import json
import logging
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.exceptions import LLMResponseError, LLMUnavailableError
from app.schemas.ai_response import AIAnalysis
from app.services.prompt_service import (
    SYSTEM_PROMPT,
    build_correction_prompt,
    build_user_prompt,
)

logger = logging.getLogger(__name__)

MAX_CALLS_PER_ANALYSIS = 2
RETRY_BACKOFF_SECONDS = 0.25
THINK_BLOCK_PATTERN = re.compile(
    r"<think\b[^>]*>.*?</think\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)


class ChatCompletions(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class ChatResource(Protocol):
    completions: ChatCompletions


class ChatClient(Protocol):
    chat: ChatResource


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMResult:
    analysis: AIAnalysis
    model_used: str
    validated_on_first_response: bool
    attempts: int
    usage: TokenUsage | None
    truncated: bool


def _strip_thinking_blocks(content: str) -> str:
    return THINK_BLOCK_PATTERN.sub("", content).strip()


def _extract_json_object(content: str) -> Mapping[str, Any]:
    cleaned_content = _strip_thinking_blocks(content)
    decoder = json.JSONDecoder()

    for index, character in enumerate(cleaned_content):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned_content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Nenhum objeto JSON válido foi encontrado na resposta.")


def _read_message_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise ValueError("A resposta não contém uma mensagem utilizável.") from exc

    if isinstance(content, str) and content.strip():
        return content

    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        text_parts: list[str] = []
        for part in content:
            part_type = (
                part.get("type")
                if isinstance(part, Mapping)
                else getattr(part, "type", None)
            )
            if part_type not in {"text", "output_text"}:
                continue
            part_text = (
                part.get("text")
                if isinstance(part, Mapping)
                else getattr(part, "text", None)
            )
            if isinstance(part_text, str):
                text_parts.append(part_text)
        if text_parts:
            return "".join(text_parts)

    raise ValueError("A resposta não contém texto utilizável.")


def _read_finish_reason(response: Any) -> str | None:
    try:
        finish_reason = response.choices[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return None
    return finish_reason if isinstance(finish_reason, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _read_usage(response: Any) -> TokenUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    token_usage = TokenUsage(
        prompt_tokens=_optional_int(getattr(usage, "prompt_tokens", None)),
        completion_tokens=_optional_int(getattr(usage, "completion_tokens", None)),
        total_tokens=_optional_int(getattr(usage, "total_tokens", None)),
    )
    if (
        token_usage.prompt_tokens is None
        and token_usage.completion_tokens is None
        and token_usage.total_tokens is None
    ):
        return None
    return token_usage


def _sum_optional(first: int | None, second: int | None) -> int | None:
    if first is None and second is None:
        return None
    return (first or 0) + (second or 0)


def _merge_usage(
    current: TokenUsage | None, new: TokenUsage | None
) -> TokenUsage | None:
    if current is None:
        return new
    if new is None:
        return current
    return TokenUsage(
        prompt_tokens=_sum_optional(current.prompt_tokens, new.prompt_tokens),
        completion_tokens=_sum_optional(
            current.completion_tokens,
            new.completion_tokens,
        ),
        total_tokens=_sum_optional(current.total_tokens, new.total_tokens),
    )


def _validation_error_summary(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return json.dumps(
            error.errors(include_input=False),
            ensure_ascii=False,
        )[:1000]
    return str(error)[:1000]


def _is_retryable_status_error(error: APIStatusError) -> bool:
    return error.status_code == 429 or error.status_code >= 500


class LLMService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: ChatClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.sleep = sleep
        self.client = client or self._build_client()

    def _build_client(self) -> OpenAI:
        if self.settings.nvidia_api_key is None:
            raise LLMUnavailableError(
                "Configure NVIDIA_API_KEY antes de solicitar uma análise."
            )
        return OpenAI(
            api_key=self.settings.nvidia_api_key.get_secret_value(),
            base_url=self.settings.nvidia_base_url,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=0,
        )

    def _request_arguments(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "model": self.settings.nvidia_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
            "stream": False,
        }
        if self.settings.llm_reasoning_enabled is not None:
            arguments["extra_body"] = {
                "chat_template_kwargs": {
                    "enable_thinking": self.settings.llm_reasoning_enabled
                }
            }
        return arguments

    def _call_model(self, messages: list[dict[str, str]]) -> Any:
        return self.client.chat.completions.create(**self._request_arguments(messages))

    def analyze(
        self,
        masked_text: str,
        category_hint: str | None = None,
    ) -> LLMResult:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(masked_text, category_hint),
            },
        ]
        usage: TokenUsage | None = None
        validation_failures = 0
        was_truncated = False

        for attempt_index in range(MAX_CALLS_PER_ANALYSIS):
            started_at = time.perf_counter()
            try:
                response = self._call_model(messages)
            except (
                APIConnectionError,
                APITimeoutError,
                ConnectionError,
                TimeoutError,
            ) as exc:
                self._handle_transport_failure(exc, attempt_index)
                continue
            except APIStatusError as exc:
                if _is_retryable_status_error(exc):
                    self._handle_transport_failure(exc, attempt_index)
                    continue
                logger.warning(
                    "LLM request rejected status=%s model=%s",
                    exc.status_code,
                    self.settings.nvidia_model,
                )
                raise LLMUnavailableError() from exc

            elapsed_ms = round((time.perf_counter() - started_at) * 1000)
            response_usage = _read_usage(response)
            usage = _merge_usage(usage, response_usage)
            finish_reason = _read_finish_reason(response)
            response_truncated = finish_reason == "length"
            was_truncated = was_truncated or response_truncated
            logger.info(
                "LLM response received model=%s attempt=%s elapsed_ms=%s "
                "finish_reason=%s total_tokens=%s",
                self.settings.nvidia_model,
                attempt_index + 1,
                elapsed_ms,
                finish_reason,
                response_usage.total_tokens if response_usage else None,
            )
            if response_truncated:
                logger.warning(
                    "LLM response may be truncated model=%s attempt=%s max_tokens=%s",
                    self.settings.nvidia_model,
                    attempt_index + 1,
                    self.settings.llm_max_tokens,
                )

            raw_content = ""
            try:
                raw_content = _read_message_content(response)
                json_object = _extract_json_object(raw_content)
                analysis = AIAnalysis.model_validate(json_object)
            except (ValidationError, ValueError) as exc:
                validation_failures += 1
                if attempt_index + 1 >= MAX_CALLS_PER_ANALYSIS:
                    message = (
                        "A resposta da IA foi truncada e não pôde ser validada. "
                        "Aumente LLM_MAX_TOKENS ou tente novamente."
                        if was_truncated
                        else None
                    )
                    raise LLMResponseError(message) from exc
                messages.extend(
                    [
                        {
                            "role": "assistant",
                            "content": _strip_thinking_blocks(raw_content),
                        },
                        {
                            "role": "user",
                            "content": build_correction_prompt(
                                _validation_error_summary(exc)
                            ),
                        },
                    ]
                )
                continue

            return LLMResult(
                analysis=analysis,
                model_used=self.settings.nvidia_model,
                validated_on_first_response=validation_failures == 0,
                attempts=attempt_index + 1,
                usage=usage,
                truncated=was_truncated,
            )

        raise LLMUnavailableError()

    def _handle_transport_failure(
        self,
        error: Exception,
        attempt_index: int,
    ) -> None:
        logger.warning(
            "LLM transport failure type=%s model=%s attempt=%s",
            type(error).__name__,
            self.settings.nvidia_model,
            attempt_index + 1,
        )
        if attempt_index + 1 >= MAX_CALLS_PER_ANALYSIS:
            raise LLMUnavailableError() from error
        self.sleep(RETRY_BACKOFF_SECONDS)
