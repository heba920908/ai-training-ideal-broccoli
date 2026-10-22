# T5: RAG Advanced

Microwave-manual assistance using plain Python, PostgreSQL/pgvector, and the OpenAI-compatible EPAM DIAL API. No LangChain, alternate-provider clients, or Ollama services are used.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>, Python task `t5_rag_advanced`.
- The complete implementation and manual are bundled in [solution/t5_rag_advanced](solution/t5_rag_advanced). The workspace clone is not required.
- Background: [../t5_rag_advanced.md](../t5_rag_advanced.md).

## Provider and Embedding Findings

Only `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` from the root `.env` are required. The script loads the nearest ancestor `.env` automatically, without overriding exported variables or printing secrets. You can also follow the earlier exercises:

```bash
set -a; source .env; set +a
```

**Yes, this RAG pipeline needs an embedding model.** It converts both document chunks and questions into vectors. The chat model configured by `OPENAI_MODEL` generates answers; it is not assumed to offer embeddings. PostgreSQL stores and compares vectors but does not generate them.

Verified against DIAL on **2026-10-22** using `GET /openai/models`:

| Deployment returned by DIAL | Verification for this exercise |
| --- | --- |
| `text-embedding-005` | Selected automatically; live embeddings succeeded with **768 dimensions**, including the full manual and question vectors. |
| `text-embedding-3-small-1` | Listed; not invoked. |
| `text-embedding-3-large-1` | Listed; not invoked. |
| `text-embedding-ada-002` | Listed; not invoked. |
| `gemini-embedding-2` | Listed; not invoked. |
| `azure-ai-vision-embeddings` | Listed; not invoked; not preferred for this text-only manual. |

Discovery prefers non-vision deployments, then IDs beginning with `text-embedding`, with alphabetical ordering within groups. `--embedding-model <deployment>` overrides discovery without another environment variable. Listed deployments are not a guarantee of access, dimensions, or retrieval quality; only the selected deployment was exercised.

Requests use `Api-Key` and DIAL deployment routes. Public OpenAI hosts are rejected. Chat used the unchanged `.env` deployment, `DeepSeek-V4-Flash-2026-04-23`, in the observed run. Neither observed model name is hard-coded in the solution, and no alternative chat model was tried.

The course's initial `VECTOR(384)` is not assumed to match DIAL. On initial indexing or explicit reload, the app uses the returned vector width and transactionally recreates the dedicated exercise table. Index metadata records embedding endpoint/model, dimensions, manual hash, chunk size, and overlap; incompatible reuse requires `--reload`. Use the same embedding deployment for indexing and querying.

## Tasks

- [x] Run local PostgreSQL/pgvector with `podman-compose`.
- [x] Load and chunk the bundled manual; generate and persist native-width embeddings.
- [x] Implement cosine and Euclidean retrieval with configurable top-k and score filtering.
- [x] Print scores, retrieved chunks, augmented prompts, and grounded responses.
- [x] Support batch, single-question, and interactive modes with bounded conversation history.
- [x] Verify transaction rollback, safe index reuse, local exports, and dimension mismatch.
- [x] Capture all seven live course examples locally without tracking output in Git.

## How to Run

Run all commands from the repository root. Requires Python 3.11+, `uv`, Podman, and `podman-compose`. Python dependencies are supplied through `uv run --with`.

### Start PostgreSQL

```bash
podman-compose -p t5-rag \
  -f app_development/t5-rag-advanced/solution/t5_rag_advanced/docker-compose.yml up -d

podman exec t5-rag_rag-pgvector_1 pg_isready -U postgres -d vectordb
```

Proceed when `pg_isready` reports `accepting connections`; initialization can still be running immediately after startup. The service uses `docker.io/pgvector/pgvector:pg16`, a persistent named volume, and **127.0.0.1:5433**, not the standard host port 5432. The local course database is `vectordb`, with disposable development credentials `postgres` / `postgres`. This setup is not for production or shared hosts. No database service outside localhost is contacted.

The bundled [init.sql](solution/t5_rag_advanced/init.sql) enables pgvector and creates the initial tables. It runs automatically only for a new volume. Application indexing adapts the vector width; exact search is intentional for this small manual, avoiding HNSW dimension restrictions.

### All Seven Examples With Captured Output

```bash
mkdir -p app_development/t5-rag-advanced/output
set -o pipefail
uv run --with httpx --with psycopg2-binary --with python-dotenv \
  --directory app_development/t5-rag-advanced/solution \
  python -u -m t5_rag_advanced.app --all --k 16 --score 0.3 \
  --export-embeddings "$PWD/app_development/t5-rag-advanced/output/embeddings.json" \
  2>&1 | tee app_development/t5-rag-advanced/output/rag_examples.txt
```

The first run indexes the manual; subsequent matching runs reuse PostgreSQL data. This command keeps the course's 300-character chunks and 40-character overlap but retrieves up to 16 chunks: the opening clock-setting step ranked 15th in the observed run. Defaults remain `--k 5 --score 0.5`; narrower retrieval can omit important neighboring instructions. `pipefail` preserves application failures when capturing output with `tee`.

`--export-embeddings` is optional. The JSON contains chunk text, numeric vectors, and index metadata for local inspection, not API credentials. It is an export, not an automatic restore source; PostgreSQL's volume provides persistence.

### One Question or Interactive Mode

```bash
uv run --with httpx --with psycopg2-binary --with python-dotenv \
  --directory app_development/t5-rag-advanced/solution \
  python -u -m t5_rag_advanced.app --query "What is the ECO function on this microwave?" \
  --k 16 --score 0.3
```

Omit `--query` and `--all` for interactive mode. Enter `quit`, `exit`, or EOF to stop. Interactive history keeps four turns, but only retrieved manual context is evidence for answers. `--manual /path/to/manual.txt` selects another manual. After changing the manual, embedding deployment, or chunk configuration, add `--reload` to explicitly replace this exercise's index. A failed reload rolls back the table replacement.

### Euclidean Distance

```bash
set -o pipefail
uv run --with httpx --with psycopg2-binary --with python-dotenv \
  --directory app_development/t5-rag-advanced/solution \
  python -u -m t5_rag_advanced.app --mode euclidean --score 0.5 \
  --query "What is the maximum cooking time that can be set on microwave?" \
  2>&1 | tee app_development/t5-rag-advanced/output/euclidean_example.txt
```

`--score` is a **minimum similarity**, not a maximum distance. Higher thresholds retain fewer results. Cosine uses `<=>` with `score = max(0, 1 - distance)`; Euclidean uses `<->` with `score = 1 / (1 + distance)`. Thresholds must satisfy `0 < score <= 1`, and the scores are not directly interchangeable between metrics. Vectors are not silently truncated or re-embedded using another model.

Correction to the background notes: pgvector's `<#>` operator is negative inner product, **not** cosine distance. The implementation uses `<=>` for cosine.

### Dimension-Mismatch Experiment

```bash
set -o pipefail
uv run --with httpx --with psycopg2-binary --with python-dotenv \
  --directory app_development/t5-rag-advanced/solution \
  python -u -m t5_rag_advanced.app --dimension-mismatch \
  2>&1 | tee app_development/t5-rag-advanced/output/dimension_mismatch.txt
```

The script pads one query vector by a single zero coordinate, without changing the embedding model. Observed database response: `different vector dimensions 768 and 769`. This expected rejection exits successfully and leaves the index unchanged. The course's Ollama/model-switch experiment is intentionally skipped under the DIAL-only scope; equal dimensions alone do not make different models' vector spaces compatible.

### Tests

Offline tests, without DIAL calls or PostgreSQL:

```bash
uv run --with pytest --with httpx --with psycopg2-binary --with python-dotenv \
  --directory app_development/t5-rag-advanced/solution \
  python -m pytest -q -k 'not Postgres'
```

For the full suite, create the isolated test database once after starting Podman:

```bash
podman exec t5-rag_rag-pgvector_1 createdb -U postgres t5_test

uv run --with pytest --with httpx --with psycopg2-binary --with python-dotenv \
  --directory app_development/t5-rag-advanced/solution \
  python -m pytest -q
```

Skip `createdb` if `t5_test` already exists. Database tests replace only their own `t5_test` tables, not the live manual in `vectordb`. All tests use deterministic embeddings or an HTTP test transport; they do not call DIAL. Optional static checks: `uv run --with ruff ruff check app_development/t5-rag-advanced/solution`.

### Inspect and Stop PostgreSQL

```bash
podman exec t5-rag_rag-pgvector_1 psql -U postgres -d vectordb \
  -c 'SELECT count(*), min(vector_dims(embedding)), max(vector_dims(embedding)) FROM vectors;'

podman-compose -p t5-rag \
  -f app_development/t5-rag-advanced/solution/t5_rag_advanced/docker-compose.yml down
```

Stopping retains the named volume. The application can use `--db-port` or `--db-name` for a different dedicated localhost exercise database; the bundled Compose service still publishes port 5433. Do not target a database containing unrelated tables named `vectors` or `rag_index`.

## Deliverables and Local Output

- [solution/t5_rag_advanced/app.py](solution/t5_rag_advanced/app.py): grounded RAG CLI and course questions.
- [solution/t5_rag_advanced/dial.py](solution/t5_rag_advanced/dial.py): DIAL discovery, vector validation, and HTTP adapter.
- [solution/t5_rag_advanced/embeddings/text_processor.py](solution/t5_rag_advanced/embeddings/text_processor.py): transactional persistence, identity checks, retrieval, export, and mismatch.
- [solution/t5_rag_advanced/test_t5_rag.py](solution/t5_rag_advanced/test_t5_rag.py): offline and real-pgvector tests.
- [solution/t5_rag_advanced/docker-compose.yml](solution/t5_rag_advanced/docker-compose.yml), initialization SQL, chat/embedding clients, chunk utility, and bundled manual.

Generated files remain visible under local `output/`, but [.gitignore](.gitignore) excludes the entire directory, Python caches, and logs. Do not force-add generated output. The local review files are `rag_examples.txt` (final), `rag_examples_initial_k8.txt`, `clock_k12.txt`, `embedding_discovery.txt`, `embeddings.json`, `dimension_mismatch.txt`, and `euclidean_example.txt`. Regenerate them with the commands above; no output is part of the recorded solution.

## Results / Notes

Verified **2026-10-22**: **21 tests passed** in both the fork and standalone solution, including four real PostgreSQL tests; Ruff passed. The live manual contains **94 chunks of 768 dimensions**. The final seven-example batch used cosine search, `--k 16 --score 0.3`, and reused the stored index. Euclidean retrieval and the mismatch experiment were also exercised against Podman PostgreSQL.

| Question | Observed final response |
| --- | --- |
| Maximum cooking time | 95 minutes. |
| Set the clock | All five steps, starting with holding POWER/CLOCK for 3 seconds to select the clock format. |
| ECO function | Power saving; DISINFECT/DEODORIZE/ECO, MENU/TIME to ECO, then START/QUICK START. |
| Smoking containers | Switch off or unplug; keep the door closed. |
| Remove odors | Water with juice and skin of one lemon; microwave 5 minutes, then wipe and dry. |
| DIALX Community | Supplied manual context contains no information. |
| Dinosaur era | Supplied manual context contains no information. |

The initial eight-chunk run omitted the opening clock step and reported incomplete context. Twelve chunks still omitted it; the step ranked 15th. Increasing to 16 retrieved it without changing models or chunk configuration. Larger retrieval sets increase prompt size and can add irrelevant context. Prompt grounding is not a security guarantee, and generated answers still need review against the printed manual passages.