from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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
