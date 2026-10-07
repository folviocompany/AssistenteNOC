from app.services.prompt_service import (
    SYSTEM_PROMPT,
    build_correction_prompt,
    build_user_prompt,
)


def test_system_prompt_contains_required_contract_rules() -> None:
    assert "somente com um objeto JSON válido" in SYSTEM_PROMPT
    assert "português do Brasil" in SYSTEM_PROMPT
    assert "não informado" in SYSTEM_PROMPT
    assert "Não invente medições" in SYSTEM_PROMPT
    assert '"prioridade": "Baixa | Média | Alta | Crítica"' in SYSTEM_PROMPT


def test_user_prompt_includes_masked_report_and_category() -> None:
    prompt = build_user_prompt("Contato [E-MAIL] com LOS aceso.", "Fibra/LOS")

    assert "Contato [E-MAIL] com LOS aceso." in prompt
    assert "Categoria selecionada pelo analista: Fibra/LOS." in prompt
    assert "<relato>" in prompt


def test_user_prompt_requests_category_inference_when_missing() -> None:
    prompt = build_user_prompt("Cliente relata lentidão.")

    assert "Categoria não selecionada" in prompt
    assert "infira a categoria" in prompt


def test_correction_prompt_requests_only_corrected_json() -> None:
    prompt = build_correction_prompt("prioridade inválida")

    assert "prioridade inválida" in prompt
    assert "somente o objeto JSON completo" in prompt
