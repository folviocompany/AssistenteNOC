import pytest
from pydantic import ValidationError

from app.schemas.ai_response import AIAnalysis, Priority


def valid_payload() -> dict[str, object]:
    return {
        "categoria": "Fibra/LOS",
        "prioridade": "Alta",
        "causa_provavel": "Atenuação elevada no enlace óptico.",
        "perguntas_para_cliente": ["O LED LOS está aceso?"],
        "testes_recomendados": ["Verificar a potência óptica da ONU."],
        "acao_sugerida": "Inspecionar conectores e possíveis dobras na fibra.",
        "relato_final": "Cliente relata indisponibilidade; necessária inspeção óptica.",
    }


def test_valid_analysis_accepts_contract_and_ignores_extra_fields() -> None:
    payload = valid_payload()
    payload["campo_extra"] = "ignorado"

    analysis = AIAnalysis.model_validate(payload)

    assert analysis.prioridade is Priority.HIGH
    assert "campo_extra" not in analysis.model_dump()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prioridade", "Urgente"),
        ("categoria", "   "),
        ("perguntas_para_cliente", []),
        ("testes_recomendados", [str(index) for index in range(9)]),
    ],
)
def test_invalid_analysis_is_rejected(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(payload)
