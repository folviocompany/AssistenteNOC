import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
HYPHEN_TRANSLATION = str.maketrans(
    {
        "\u00ad": "-",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2043": "-",
        "\u2212": "-",
        "\ufe58": "-",
        "\ufe63": "-",
        "\uff0d": "-",
    }
)
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", value.translate(HYPHEN_TRANSLATION)).strip()


class Priority(StrEnum):
    LOW = "Baixa"
    MEDIUM = "Média"
    HIGH = "Alta"
    CRITICAL = "Crítica"


class AIAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    categoria: NonEmptyText
    prioridade: Priority
    causa_provavel: NonEmptyText
    perguntas_para_cliente: list[NonEmptyText] = Field(min_length=1, max_length=8)
    testes_recomendados: list[NonEmptyText] = Field(min_length=1, max_length=8)
    acao_sugerida: NonEmptyText
    relato_final: NonEmptyText

    @field_validator("*", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_text(value)
        if isinstance(value, (list, tuple)):
            return [
                normalize_text(item) if isinstance(item, str) else item
                for item in value
            ]
        return value
