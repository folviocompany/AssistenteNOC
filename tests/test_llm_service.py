import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import Settings
from app.exceptions import LLMResponseError, LLMUnavailableError
from app.services.llm_service import APIStatusError, LLMService


def valid_payload() -> dict[str, object]:
    return {
        "categoria": "Quedas",
        "prioridade": "Alta",
        "causa_provavel": "Instabilidade no enlace.",
        "perguntas_para_cliente": ["Quando as quedas começaram?"],
        "testes_recomendados": ["Validar níveis de sinal."],
        "acao_sugerida": "Monitorar o enlace e revisar conectores.",
        "relato_final": "Cliente relata quedas; enlace deve ser verificado.",
    }


def fake_response(
    content: str,
    *,
    reasoning_content: str | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 20,
    completion_tokens: int = 30,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    reasoning_content=reasoning_content,
                ),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


class FakeCompletions:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.completions = FakeCompletions(outcomes)
        self.chat = SimpleNamespace(completions=self.completions)


def fake_status_error(status_code: int) -> APIStatusError:
    response = SimpleNamespace(status_code=status_code, request=object(), headers={})
    return APIStatusError("erro simulado", response=response, body=None)


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_valid_json_is_validated_on_first_response() -> None:
    client = FakeClient([fake_response(json.dumps(valid_payload()))])
    service = LLMService(settings=settings(), client=client)

    result = service.analyze("Relato mascarado.")

    assert result.analysis.categoria == "Quedas"
    assert result.validated_on_first_response is True
    assert result.attempts == 1
    assert result.usage is not None
    assert result.usage.total_tokens == 50
    assert len(client.completions.calls) == 1
    assert "extra_body" not in client.completions.calls[0]


def test_extracts_json_from_fence_and_surrounding_text() -> None:
    content = f"Resposta solicitada:\n```json\n{json.dumps(valid_payload())}\n```\nFim."
    service = LLMService(
        settings=settings(),
        client=FakeClient([fake_response(content)]),
    )

    result = service.analyze("Relato mascarado.")

    assert result.analysis.prioridade == "Alta"


def test_ignores_think_blocks_and_separate_reasoning_field() -> None:
    content = '<think>Vou raciocinar {"rascunho": true}.</think>' + json.dumps(
        valid_payload()
    )
    response = fake_response(
        content,
        reasoning_content='{"nao_deve_ser": "extraido"}',
    )
    service = LLMService(settings=settings(), client=FakeClient([response]))

    result = service.analyze("Relato mascarado.")

    assert result.analysis.categoria == "Quedas"
    assert result.attempts == 1


def test_invalid_json_is_corrected_on_single_retry() -> None:
    first = fake_response("não é JSON", prompt_tokens=10, completion_tokens=5)
    second = fake_response(
        json.dumps(valid_payload()), prompt_tokens=30, completion_tokens=20
    )
    client = FakeClient([first, second])
    service = LLMService(settings=settings(), client=client)

    result = service.analyze("Relato mascarado.")

    assert result.validated_on_first_response is False
    assert result.attempts == 2
    assert result.usage is not None
    assert result.usage.total_tokens == 65
    correction_messages = client.completions.calls[1]["messages"]
    assert "não atende ao contrato JSON" in correction_messages[-1]["content"]


def test_invalid_json_twice_raises_controlled_error() -> None:
    client = FakeClient([fake_response("inválido"), fake_response("ainda inválido")])
    service = LLMService(settings=settings(), client=client)

    with pytest.raises(LLMResponseError):
        service.analyze("Relato mascarado.")

    assert len(client.completions.calls) == 2


def test_timeout_retries_once_without_real_network() -> None:
    sleeps: list[float] = []
    client = FakeClient(
        [TimeoutError("timeout simulado"), fake_response(json.dumps(valid_payload()))]
    )
    service = LLMService(
        settings=settings(),
        client=client,
        sleep=sleeps.append,
    )

    result = service.analyze("Relato mascarado.")

    assert result.attempts == 2
    assert len(client.completions.calls) == 2
    assert sleeps == [0.25]


def test_timeout_twice_raises_unavailable_error() -> None:
    client = FakeClient([TimeoutError("primeiro"), TimeoutError("segundo")])
    service = LLMService(
        settings=settings(),
        client=client,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(LLMUnavailableError):
        service.analyze("Relato mascarado.")

    assert len(client.completions.calls) == 2


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_retryable_api_status_retries_once(status_code: int) -> None:
    client = FakeClient(
        [fake_status_error(status_code), fake_response(json.dumps(valid_payload()))]
    )
    service = LLMService(
        settings=settings(),
        client=client,
        sleep=lambda _seconds: None,
    )

    result = service.analyze("Relato mascarado.")

    assert result.attempts == 2
    assert len(client.completions.calls) == 2


def test_non_retryable_api_status_fails_without_retry() -> None:
    client = FakeClient([fake_status_error(400)])
    service = LLMService(settings=settings(), client=client)

    with pytest.raises(LLMUnavailableError):
        service.analyze("Relato mascarado.")

    assert len(client.completions.calls) == 1


def test_optional_reasoning_parameter_is_only_sent_when_configured() -> None:
    client = FakeClient([fake_response(json.dumps(valid_payload()))])
    service = LLMService(
        settings=settings(llm_reasoning_enabled=False),
        client=client,
    )

    service.analyze("Relato mascarado.")

    assert client.completions.calls[0]["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


def test_truncated_response_is_reported_when_json_is_still_valid() -> None:
    response = fake_response(json.dumps(valid_payload()), finish_reason="length")
    service = LLMService(settings=settings(), client=FakeClient([response]))

    result = service.analyze("Relato mascarado.")

    assert result.truncated is True
