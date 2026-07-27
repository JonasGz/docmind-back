# DocMind API

API do DocMind, um assistente jurídico que responde perguntas a partir dos PDFs
privados enviados por cada usuário. O projeto combina FastAPI, LangChain,
PostgreSQL com pgvector, armazenamento compatível com S3 e modelos da OpenAI
para implementar um fluxo de **RAG (Retrieval-Augmented Generation)** com
fontes rastreáveis.

> A resposta é limitada ao conteúdo recuperado dos documentos do usuário. O
> sistema não substitui análise ou aconselhamento jurídico profissional.

## Sumário

- [Visão geral](#visão-geral)
- [IA e conceitos aplicados](#ia-e-conceitos-aplicados)
- [Arquitetura](#arquitetura)
- [Arquitetura RAG](#arquitetura-rag)
- [Fluxos principais](#fluxos-principais)
- [Tecnologias](#tecnologias)
- [Como executar](#como-executar)
- [Configuração](#configuração)
- [Rotas da API](#rotas-da-api)
- [Modelo de dados](#modelo-de-dados)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Testes](#testes)

## Visão geral

O DocMind recebe PDFs jurídicos, extrai o texto, segmenta-o em trechos,
transforma os trechos em embeddings e os indexa no `pgvector`. Em uma pergunta,
o backend encontra os trechos semanticamente mais relevantes, monta um prompt
com contexto e histórico da conversa e pede à LLM uma resposta fundamentada.

Cada documento e cada busca são sempre vinculados ao usuário autenticado. O
resultado de uma resposta inclui as fontes usadas, com documento, página,
similaridade e trecho de apoio.

## IA e conceitos aplicados

| Conceito ou ferramenta                             | Como é usado no DocMind                                                                                             |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **RAG baseado em busca vetorial por similaridade** | Complementa a pergunta com trechos recuperados dos PDFs antes da geração da resposta.                               |
| **LangChain**                                      | O `RecursiveCharacterTextSplitter` faz a segmentação recursiva dos textos, com separadores próprios para legislação. |
| **LLM**                                            | `gpt-4o-mini`, configurável por ambiente, gera respostas fundamentadas e extrai metadados dos documentos.           |
| **Embeddings**                                     | `text-embedding-3-large` transforma chunks e perguntas em vetores semânticos de 1.536 dimensões.                    |
| **Busca semântica**                                | O pgvector compara a pergunta com os chunks por distância de cosseno, em vez de depender apenas de palavras exatas. |
| **Índice HNSW**                                    | Índice vetorial aproximado que acelera a busca por vizinhos semanticamente próximos.                                |
| **Grounding**                                      | O prompt restringe a LLM ao contexto recuperado e exige citações de documento e página.                             |
| **Limiar de similaridade**                         | Descarta resultados pouco relevantes; sem contexto suficiente, a LLM não é chamada.                                 |
| **Seleção de documento-alvo**                      | Identificadores e uma classificação JSON por LLM reduzem a mistura de conteúdo entre documentos.                    |
| **Memória conversacional limitada**                | As últimas mensagens da conversa são incluídas para preservar contexto sem crescer indefinidamente.                 |

## Arquitetura

O backend segue uma arquitetura em camadas pragmática. As fronteiras são
concretas, sem interfaces abstratas desnecessárias:

```text
Cliente HTTP
    │
    ▼
FastAPI / Routers ── validação e contrato HTTP (Pydantic)
    │
    ▼
Services ────────── regras de negócio e orquestração dos casos de uso
    │                         │
    │                         ├── rag/ ─────── parsing, chunking e prompt
    │                         ├── llm.py ──── OpenAI (chat e embeddings)
    │                         └── storage/ ─ MinIO/S3
    ▼
Repositories ────── persistência e consultas isoladas do ORM
    │
    ▼
SQLAlchemy ──────── PostgreSQL + pgvector
```

| Camada          | Responsabilidade                                                   | Exemplos                                 |
| --------------- | ------------------------------------------------------------------ | ---------------------------------------- |
| `routers/`      | Expõe endpoints, converte erros em HTTP e agenda tarefas de fundo. | `documents.py`, `conversations.py`       |
| `schemas/`      | Define payloads e respostas da API com Pydantic.                   | `DocumentResponse`, `MessageResponse`    |
| `services/`     | Coordena regras de negócio.                                        | upload, ingestão, recuperação e chat     |
| `repositories/` | Encapsula as consultas SQLAlchemy e mantém o filtro por usuário.   | `ChunkRepository`, `DocumentRepository`  |
| `rag/`          | Implementa os componentes específicos do RAG.                      | loader PDF, splitter, metadados, prompt  |
| `models/`       | Mapeia as tabelas do domínio.                                      | usuários, documentos, chunks e conversas |
| `storage/`      | Encapsula o object storage S3-compatível.                          | upload, download e URL pré-assinada      |

O LangChain não é uma camada arquitetural e não controla o fluxo da aplicação:
ele é usado apenas como biblioteca interna pelo módulo `rag/splitter.py`, por
meio do `RecursiveCharacterTextSplitter`. A extração de PDF é feita com
`pypdf`, as chamadas à OpenAI ficam centralizadas em `app/llm.py` e a busca
vetorial é uma consulta SQLAlchemy/pgvector.

## Arquitetura RAG

O DocMind usa **RAG baseado em busca vetorial por similaridade** (_Vector-based
RAG_), com indexação antecipada (_offline ingestion_) e recuperação no momento
da pergunta (_online retrieval_). A busca semântica é a técnica de recuperação
do RAG: ela encontra trechos por proximidade entre embeddings antes de a LLM
gerar a resposta.

```text
PDF → MinIO → extração por página → chunking → embeddings → pgvector/HNSW
                                                           │
Pergunta → embedding → busca por cosseno + filtros ───────┘
                     │
                     ▼
      contexto agrupado por documento + histórico recente
                     │
                     ▼
                LLM → resposta + fontes
```

### Ingestão e indexação

1. O PDF é validado e salvo no MinIO; o registro do documento entra como
   `processing`.
2. O FastAPI agenda `processar_documento` em `BackgroundTasks`. Isso evita
   bloquear a resposta do upload, sem introduzir uma fila externa nesta versão.
3. O `pypdf` extrai texto de cada página. PDFs sem texto extraível (por exemplo,
   documentos digitalizados que dependem de OCR) são marcados como `failed`.
4. O `RecursiveCharacterTextSplitter` gera chunks de até 1.000 caracteres, com
   sobreposição de 400 caracteres. Em textos legislativos com ao menos três
   ocorrências de `Art.`, o splitter usa separadores que preservam artigo e
   parágrafo; `keep_separator="start"` mantém o cabeçalho normativo no trecho.
5. A LLM extrai metadados dos primeiros chunks: título, espécie do documento,
   categoria e identificadores. Se essa etapa falhar, a indexação continua.
6. `text-embedding-3-large` cria vetores truncados/configurados para 1.536
   dimensões. Os chunks, a página e o vetor são persistidos em
   `document_chunks`.
7. O documento recebe metadados, contagens e status `indexed`. Em falhas, o
   erro é registrado e o status passa para `failed`.

### Recuperação e geração

1. A pergunta é associada somente aos documentos `indexed` do usuário.
2. O _document matcher_ tenta identificar se a pergunta menciona documentos
   específicos: primeiro por identificadores textuais e, como fallback, por uma
   classificação JSON feita pela LLM sobre o catálogo de metadados dos documentos
   do usuário. Sem alvo explícito, a busca cobre todos os documentos desse usuário.
3. A pergunta recebe embedding e o `ChunkRepository` busca os `top 5` chunks
   por distância de cosseno, sempre com `user_id` como filtro obrigatório e,
   quando aplicável, com os documentos-alvo.
4. Apenas resultados com similaridade de pelo menos `0,50` seguem para a LLM. O
   limiar é um parâmetro de calibração, ajustável por ambiente conforme o acervo.
   Sem contexto suficiente, a API retorna uma resposta padronizada e não chama
   o modelo gerador.
5. Os chunks recuperados são agrupados por documento e página no prompt. O
   histórico é limitado às últimas 10 mensagens configuradas.
6. A LLM recebe regras para citar documento e página, explicitar divergências,
   não preencher lacunas com conhecimento geral e não oferecer aconselhamento
   jurídico. A mensagem do assistente é salva junto das fontes utilizadas.

### Garantias e limites do RAG

- **Isolamento:** a consulta vetorial exige `user_id`; não há busca global de
  chunks no repositório, com o objetivo de preservar o contexto de documentos privados do usuário (contratos confidenciais, etc).
- **Rastreabilidade:** cada fonte salva documento, página, score e excerto.
- **Redução de alucinação:** limiar de similaridade e resposta sem LLM quando a
  busca não retorna contexto suficiente.
- **Redução de contaminação entre documentos:** contexto rotulado e agrupado
  por documento, além da detecção de documento-alvo.
- **Limite atual:** não há OCR; PDFs constituídos apenas por imagem falham na
  extração de texto, fica para a v2.
- **Limite operacional:** `BackgroundTasks` não sobrevive a reinícios do
  processo. Documentos em `processing` por mais de 15 minutos são apresentados
  como falhos na listagem; fila fica para a v2.

## Fluxos principais

### Autenticação

```text
Google Sign-In (id_token) → POST /auth/google → validação com Google
→ cria/localiza usuário por e-mail → JWT próprio (access + refresh)
→ Bearer token nas rotas protegidas
```

O backend usa Google Sign-In como prova de identidade e emite seus próprios
JWTs. O token de acesso dura 30 minutos por padrão e o refresh token, 30 dias.

### Upload de documento

```text
POST /documents (PDF)
→ valida tipo e tamanho
→ salva original no MinIO
→ cria documento no PostgreSQL (processing)
→ retorna 202 Accepted
→ BackgroundTasks executa o pipeline de indexação
```

O upload ao storage e o commit do banco não compartilham transação. Se o commit
falhar após o upload, o serviço remove o objeto recém-criado para reduzir a
possibilidade de arquivos órfãos.

### Pergunta em uma conversa

```text
POST /conversations/{id}/messages
→ salva pergunta
→ recuperação vetorial isolada por usuário
→ sem contexto: resposta padronizada
→ com contexto: prompt + histórico + LLM
→ salva resposta e fontes → retorna mensagem
```

## Tecnologias

- **API:** FastAPI e Pydantic
- **Persistência:** SQLAlchemy, Alembic e PostgreSQL 17
- **Vetores:** extensão pgvector, distância de cosseno e índice HNSW
- **IA:** OpenAI (`gpt-4o-mini` e `text-embedding-3-large` por padrão)
- **Chunking:** LangChain Text Splitters
- **PDF:** pypdf
- **Object storage:** MinIO via `boto3`/S3
- **Autenticação:** verificação de Google ID Token e JWT (`PyJWT`)
- **Ambiente:** Docker Compose e `uv`/Python 3.13

## Como executar

### Pré-requisitos

- Docker e Docker Compose, para PostgreSQL/pgvector e MinIO;
- Python 3.13 e [uv](https://docs.astral.sh/uv/), para executar a API fora do
  container;
- uma chave da OpenAI e um Client ID OAuth 2.0 do Google para usar IA e login.

### 1. Configure as variáveis de ambiente

```bash
cd docmind-back
cp .env.example .env
```

Preencha ao menos `OPENAI_API_KEY` e `GOOGLE_CLIENT_ID` no `.env`. Em produção,
defina também um `JWT_SECRET` forte; a aplicação valida essas configurações ao
iniciar.

### 2. Inicie a infraestrutura

```bash
docker compose up -d postgres minio
```

### 3. Instale dependências e aplique as migrações

```bash
uv sync --all-groups
uv run alembic upgrade head
```

### 4. Execute a API

```bash
uv run fastapi dev app/main.py
```

A API estará em `http://localhost:8000`, a documentação interativa em
`http://localhost:8000/docs` e o console do MinIO em
`http://localhost:9001`.

Como alternativa, execute a stack inteira em containers:

```bash
docker compose up --build
```

Nesse modo, as migrações ainda devem ser aplicadas antes de usar as tabelas,
por exemplo: `docker compose exec api uv run alembic upgrade head`.

## Configuração

As configurações vêm do arquivo `.env` (veja `.env.example`). As mais relevantes
para o RAG são:

| Variável                   |                   Padrão | Finalidade                                                              |
| -------------------------- | -----------------------: | ----------------------------------------------------------------------- |
| `LLM_MODEL`                |            `gpt-4o-mini` | Modelo de geração e extração de metadados.                              |
| `EMBEDDING_MODEL`          | `text-embedding-3-large` | Modelo que cria embeddings.                                             |
| `EMBEDDING_DIMENSIONS`     |                   `1536` | Dimensão do vetor, compatível com a coluna pgvector.                    |
| `CHUNK_SIZE`               |                   `1000` | Tamanho máximo aproximado de cada chunk.                                |
| `CHUNK_OVERLAP`            |                    `400` | Sobreposição entre chunks consecutivos.                                 |
| `RETRIEVAL_TOP_K`          |                      `5` | Máximo de trechos retornados pela busca.                                |
| `SIMILARITY_THRESHOLD`     |                   `0.50` | Score mínimo para um chunk entrar no prompt.                            |
| `HISTORY_MESSAGE_COUNT`    |                     `10` | Janela de mensagens recentes enviada ao modelo.                         |
| `MAX_UPLOAD_MB`            |                     `20` | Limite de tamanho para PDFs.                                            |
| `STUCK_PROCESSING_MINUTES` |                     `15` | Tempo após o qual um processamento pendente é considerado interrompido. |
| `PRESIGNED_URL_MINUTES`    |                     `10` | Validade da URL temporária para baixar um PDF.                          |

## Rotas da API

As rotas, exceto `/health` e `/auth/google`, exigem o cabeçalho:

```http
Authorization: Bearer <access_token>
```

| Método   | Rota                                        | Autenticação | Descrição                                                        |
| -------- | ------------------------------------------- | ------------ | ---------------------------------------------------------------- |
| `GET`    | `/health`                                   | Não          | Retorna o estado básico da API.                                  |
| `POST`   | `/auth/google`                              | Não          | Recebe `id_token` do Google e devolve access/refresh tokens.     |
| `POST`   | `/auth/refresh`                             | Não          | Troca um refresh token por um novo par de tokens.                |
| `GET`    | `/auth/me`                                  | Sim          | Retorna o usuário autenticado.                                   |
| `POST`   | `/documents`                                | Sim          | Faz upload de um PDF via `multipart/form-data`; responde `202`.  |
| `GET`    | `/documents`                                | Sim          | Lista documentos do usuário e atualiza processamentos travados.  |
| `GET`    | `/documents/{document_id}`                  | Sim          | Obtém os metadados e status de um documento.                     |
| `GET`    | `/documents/{document_id}/download`         | Sim          | Cria URL pré-assinada, temporária, para baixar o PDF.            |
| `DELETE` | `/documents/{document_id}`                  | Sim          | Exclui o arquivo no storage e o registro no banco.               |
| `POST`   | `/conversations`                            | Sim          | Cria uma conversa.                                               |
| `GET`    | `/conversations`                            | Sim          | Lista conversas do usuário.                                      |
| `GET`    | `/conversations/{conversation_id}/messages` | Sim          | Lista mensagens da conversa.                                     |
| `POST`   | `/conversations/{conversation_id}/messages` | Sim          | Envia uma pergunta e recebe a mensagem do assistente com fontes. |
| `DELETE` | `/conversations/{conversation_id}`          | Sim          | Exclui uma conversa.                                             |

### Exemplos de payloads

Login com Google:

```json
POST /auth/google
{
  "id_token": "token_id_emitido_pelo_google"
}
```

Criar conversa:

```json
POST /conversations
{
  "title": "Análise do contrato de locação"
}
```

Enviar pergunta:

```json
POST /conversations/{conversation_id}/messages
{
  "content": "Qual é a multa rescisória prevista no contrato?"
}
```

Resposta de mensagem (campos principais):

```json
{
  "id": "...",
  "role": "assistant",
  "content": "A multa prevista é ... (Contrato de Locação, p. 4).",
  "sources": [
    {
      "document_id": "...",
      "document_title": "Contrato de Locação",
      "page": 4,
      "score": 0.8123,
      "excerpt": "..."
    }
  ],
  "created_at": "2026-07-26T...Z"
}
```

## Modelo de dados

| Entidade          | Papel                                                                                 |
| ----------------- | ------------------------------------------------------------------------------------- |
| `users`           | Identidade do usuário por e-mail e `google_sub`.                                      |
| `documents`       | PDF original, status da indexação e metadados extraídos.                              |
| `document_chunks` | Texto segmentado, página, vetor de 1.536 dimensões e referência ao usuário/documento. |
| `conversations`   | Conversas pertencentes ao usuário.                                                    |
| `messages`        | Perguntas e respostas; respostas podem guardar as fontes em JSONB.                    |

As chaves estrangeiras usam `ON DELETE CASCADE`. O índice HNSW de
`document_chunks.embedding` usa `vector_cosine_ops` para acelerar buscas por
similaridade de cosseno.

## Estrutura do projeto

```text
docmind-back/
├── app/
│   ├── database/       # engine, sessão e base SQLAlchemy
│   ├── models/         # entidades ORM
│   ├── rag/            # loader, splitter, metadados, matcher e prompt
│   ├── repositories/   # consultas e persistência
│   ├── routers/        # endpoints FastAPI
│   ├── schemas/        # contratos Pydantic
│   ├── services/       # casos de uso
│   ├── storage/        # adaptador S3/MinIO
│   ├── config.py       # configurações por ambiente
│   ├── dependencies.py # autenticação e injeção de sessão
│   ├── llm.py          # cliente OpenAI centralizado
│   └── main.py         # aplicação e lifespan
├── alembic/            # migrações do banco
├── tests/              # testes de ingestão, retrieval, chat e isolamento
├── docker-compose.yml  # PostgreSQL/pgvector, MinIO e API
└── .env.example        # referência das variáveis de ambiente
```

## Testes

Com PostgreSQL disponível na porta configurada para testes (por padrão,
`localhost:5435`), execute:

```bash
cd docmind-back
uv run pytest
```

A suíte cobre ingestão, recuperação vetorial, isolamento entre usuários e o
fluxo de chat.

## Próximas evoluções naturais

- substituir `BackgroundTasks` por uma fila durável no padrão _outbox_ sobre a
  própria tabela `documents`, consumida com `SELECT ... FOR UPDATE SKIP LOCKED`;
- acrescentar OCR para PDFs digitalizados;
- reprocessamento e versionamento de documentos;
- observabilidade do pipeline RAG (latência, custos, qualidade e avaliações);
- filtros explícitos por documento e re-ranking mais avançado.
