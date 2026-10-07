import argparse
import json
import logging
import time
from pathlib import Path

from app.services.llm_service import LLMService, TokenUsage
from app.services.masking_service import mask_personal_data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Executa manualmente uma análise real na API configurada.",
        epilog=(
            "Para modelos NVIDIA compatíveis, defina LLM_REASONING_ENABLED=false "
            "no .env para solicitar raciocínio desativado. Deixe vazio para não "
            "enviar esse parâmetro específico do provedor."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Relato a analisar.")
    source.add_argument(
        "--file",
        type=Path,
        help="Arquivo UTF-8 local contendo o relato.",
    )
    parser.add_argument(
        "--category", help="Categoria opcional escolhida pelo analista."
    )
    return parser


def _read_text(arguments: argparse.Namespace) -> str:
    if arguments.file is not None:
        return arguments.file.read_text(encoding="utf-8")
    return arguments.text


def _format_usage(usage: TokenUsage | None) -> str:
    if usage is None:
        return "não informado pela API"
    return (
        f"entrada={usage.prompt_tokens}, saída={usage.completion_tokens}, "
        f"total={usage.total_tokens}"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _build_parser().parse_args()
    original_text = _read_text(arguments)
    masked_text = mask_personal_data(original_text)
    service = LLMService()

    started_at = time.perf_counter()
    result = service.analyze(masked_text, arguments.category)
    elapsed_seconds = time.perf_counter() - started_at

    logging.info("Tempo total: %.2f s", elapsed_seconds)
    logging.info("Tentativas de chamada: %s", result.attempts)
    logging.info("Tokens usados: %s", _format_usage(result.usage))
    logging.info(
        "JSON válido na primeira resposta: %s",
        "sim" if result.validated_on_first_response else "não",
    )
    logging.info("Resposta truncada: %s", "sim" if result.truncated else "não")
    logging.info(
        "Análise validada:\n%s",
        json.dumps(
            result.analysis.model_dump(mode="json"), ensure_ascii=False, indent=2
        ),
    )


if __name__ == "__main__":
    main()
