# AGENTS.md — NOC AI Assistant (Python)

Regras fixas do projeto. Leia este arquivo inteiro antes de qualquer tarefa e siga-o em todas as fases.

## 1. Visão do projeto

Assistente web em Python para analistas N1/N2 e NOC de provedores de internet (ISP). O analista cola o relato de um chamado técnico e recebe: categoria, prioridade, causa provável, perguntas para o cliente, testes recomendados, ação sugerida e um **relato final padronizado** pronto para copiar.

Objetivo de portfólio: demonstrar integração **robusta** com LLM (saída estruturada, validação, retry, cache, mascaramento de dados, testes sem rede) com **poucas requisições**.

## 2. Stack (obrigatória)

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.12+ |
| Web | FastAPI + Uvicorn |
| Templates | Jinja2 (HTML server-side, CSS simples; sem React no MVP) |
| Banco | SQLite |
| ORM | SQLAlchemy 2.x (estilo moderno, `Mapped[...]`) |
| Validação/config | Pydantic v2 + pydantic-settings |
| LLM | SDK `openai` apontando para a API da NVIDIA (`https://integrate.api.nvidia.com/v1`) |
| Testes | pytest + httpx (TestClient) |
| Lint/format | ruff |

Não adicionar dependências fora desta lista sem justificar e pedir aprovação.

## 3. Regras de arquitetura

1. **Camadas**: `routes` (HTTP) → `services` (regra de negócio) → `models`/`database` (persistência). Rotas nunca falam direto com o LLM nem com o banco além de dependências injetadas.
2. **Cliente LLM isolado** em `services/llm_service.py`. Nenhum outro módulo importa `openai`. Isso permite trocar de provedor e mockar nos testes.
3. **Config só via `config.py`** (pydantic-settings, lendo `.env`). Nada de `os.environ` espalhado. Nenhuma chave no código.
4. **Resposta do LLM sempre validada** com Pydantic (`schemas/ai_response.py`). Nunca confiar em JSON cru.
5. **Provedor-agnóstico**: não depender de recursos exclusivos da NVIDIA (guided decoding etc.). Pedir JSON no prompt, extrair e validar.
6. **Modelo configurável** por variável de ambiente (`NVIDIA_MODEL`). Não fixar nome de modelo no código além do valor default em `config.py`. Conferir o catálogo atual em build.nvidia.com ao definir o default.
7. **Poucas requisições** é requisito de projeto: cache por hash, `max_tokens` limitado, no máximo **1 retry** por análise, timeout explícito.

## 4. Segurança e privacidade (inegociável)

- Antes de enviar texto ao LLM, **mascarar dados pessoais**: CPF, CNPJ, e-mail, telefone. Mascarar também sequências que pareçam documento. Manter dados técnicos (IP, MAC, RSSI, SNR, VLAN, potência óptica) pois são necessários ao diagnóstico.
- O texto **original** fica só no SQLite local; o texto **mascarado** é o que vai para a API.
- Nunca logar o relato completo nem a chave de API. Logar apenas ids, tamanhos e tempos.
- `.env` no `.gitignore`; manter `.env.example` sem valores reais.
- Limitar o tamanho do relato (ex.: 6000 caracteres) e rejeitar vazio/só espaços.
- Escapar HTML na renderização (Jinja2 autoescape ligado). Nunca usar `|safe` em conteúdo vindo do usuário ou do LLM.

## 5. Contrato de resposta da IA

O schema `AIAnalysis` (Pydantic) deve ter exatamente estes campos:

```json
{
  "categoria": "string",
  "prioridade": "Baixa | Média | Alta | Crítica",
  "causa_provavel": "string",
  "perguntas_para_cliente": ["string"],
  "testes_recomendados": ["string"],
  "acao_sugerida": "string",
  "relato_final": "string"
}
```

Regras: `prioridade` é enum; listas com 1–8 itens; strings não vazias; campos extras ignorados. O prompt de sistema deve instruir: responder **somente JSON**, em português do Brasil, linguagem técnica de NOC/suporte, sem inventar medições que não estejam no relato, e dizer "não informado" quando faltar dado.

## 6. Tratamento de erros

- Falha de rede/timeout/429/5xx da API: 1 retry com backoff curto; depois erro claro ao usuário (HTTP 502/503 com mensagem amigável em português).
- JSON inválido ou fora do schema: **1 nova tentativa** informando ao modelo o erro de validação; se falhar de novo, erro 502 controlado e nada salvo.
- Exceções do projeto em `exceptions.py`, convertidas em respostas HTTP por handlers globais. Nunca vazar stack trace ao usuário.

## 7. Estilo de código

- Type hints em tudo; funções pequenas; nomes em inglês no código, textos de interface e prompts em português do Brasil.
- Sem `print`; usar `logging`.
- Sem código morto, sem TODO solto, sem comentários óbvios.
- Docstring curta só onde a intenção não é evidente.
- `ruff check` e `ruff format` devem passar.

## 8. Estrutura de pastas

```
noc-ai-assistant/
  app/
    main.py
    config.py
    database.py
    exceptions.py
    models/
      ticket_analysis.py
    schemas/
      ticket.py
      ai_response.py
    services/
      llm_service.py
      prompt_service.py
      masking_service.py
      cache_service.py
      analysis_service.py
    routes/
      web.py
    templates/
      base.html
      new_analysis.html
      analysis_detail.html
      history.html
    static/
      css/style.css
  tests/
    conftest.py
    test_masking_service.py
    test_prompt_service.py
    test_ai_response_schema.py
    test_llm_service.py
    test_analysis_service.py
    test_routes.py
  .env.example
  .gitignore
  requirements.txt
  README.md
  AGENTS.md
```

## 9. Testes

- **Nenhum teste chama a API real.** O cliente LLM é sempre mockado/fakeado.
- Cobrir: mascaramento, schema (válido/inválido), retry de JSON inválido, cache hit/miss, rotas principais, erro da API.
- Banco de testes: SQLite em memória.
- `pytest` deve passar do zero com um comando.

## 10. Modo de trabalho

- Trabalhar por **checkpoints**. Ao fim de cada checkpoint: parar, resumir o que foi feito (arquivos criados/alterados, comandos rodados, resultado dos testes) e **aguardar liberação** antes de continuar.
- Não antecipar checkpoints futuros nem criar funcionalidades fora do escopo da fase atual.
- Se algo do prompt contradisser este arquivo, apontar a contradição e perguntar antes de agir.
- Se precisar assumir algo, listar a suposição no relatório do checkpoint.
- Antes de afirmar que algo funciona, rodar o comando e mostrar a saída.

## 11. Fora de escopo (por enquanto)

Autenticação, base de conhecimento em tabela, regras locais de diagnóstico, dashboard, upload de logs, RAG, frontend em React, deploy. Entram em fases futuras.
