# T6: AI Grounding

Compare batch LLM search, API input grounding, FAISS input grounding, and Chroma input-output grounding against a local synthetic user service. Chat and embeddings use the OpenAI-compatible **EPAM DIAL** API, not public OpenAI.

## Source

- Course: <https://github.com/epam/ai-applications-development-from-api-to-agents>, Python task `t6_grounding`.
- The complete standalone implementation is bundled in [solution/t6_grounding](solution/t6_grounding). The workspace clone is not required.
- Background and diagrams: [../t6_grounding.md](../t6_grounding.md).

## Tasks

- [x] Run the local mock user service with Podman.
- [x] Complete parallel batch search and token tracking for the baseline.
- [x] Extract explicit API search fields with a validated schema.
- [x] Implement FAISS similarity retrieval and grounded answer generation.
- [x] Implement Chroma biography retrieval, incremental synchronization, and structured hobby groups.
- [x] Validate generated IDs and fetch authoritative user details after generation.
- [x] Capture live matches, no matches, and an offline invalid/deleted-ID demonstration.
- [x] Verify the fork and standalone solution with offline tests and lint.

## Provider and Data Boundaries

Only `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` from the repository-root `.env` are required. The application finds the nearest ancestor `.env` automatically and does not override exported variables or print credentials. The example configuration is [../../.env.example](../../.env.example); the live `.env` is never copied into the solution.

Use a DIAL deployment URL such as `https://ai-proxy.lab.epam.com/openai/deployments/<deployment-name>` and put that deployment name in `OPENAI_MODEL`. DIAL requests use `Api-Key` authentication. Public OpenAI hosts, non-HTTPS provider URLs, and credential-bearing URLs are rejected. The configured chat model is used unchanged; no model-specific temperature or reasoning parameters are assumed.

**Vector modes also need an embedding deployment.** The script discovers candidates with `GET /openai/models`, preferring text embedding IDs over vision IDs. `--embedding-model "<embedding-deployment>"` overrides discovery without another environment variable. Vectors retain the provider's native dimensions; there is no fixed 384-dimensional assumption or silent model fallback. Selection does not guarantee access or retrieval quality.

The mock service creates synthetic records, including payment and personal fields. Only `id`, `name`, `surname`, `email`, and `about_me` are permitted in prompts, returned records, and captures. Chroma embeds and prompts with only `id` and `about_me`. Do not point this training workflow at real personal data. The service itself remains localhost-only at **127.0.0.1:8041**.

Structured generation uses schema instructions plus strict local Pydantic validation. It does not assume that every DIAL deployment supports native `response_format` schemas. Invalid JSON or schema violations fail the run rather than being silently repaired or accepted.

## How to Run

Run all commands from the repository root. Requires Python 3.11+, `uv`, Podman, and `podman-compose`. Dependencies are declared in [solution/t6_grounding/requirements.txt](solution/t6_grounding/requirements.txt) and supplied through `uv run`.

### Start the User Service

```bash
podman-compose -p t6-grounding \
  -f app_development/t6-grounding/solution/t6_grounding/docker-compose.yml up -d

curl --fail http://127.0.0.1:8041/health

curl --fail --silent http://127.0.0.1:8041/v1/users | jq length
```

Proceed after the health endpoint succeeds. Startup can still be in progress immediately after `up -d`; rerun the health check if necessary. Swagger is available at <http://127.0.0.1:8041/docs>.

The Compose file requests **24 initial users** with `USERS_NUMBER`, the variable actually supported by the image. The original course's `USER_COUNT` is ignored by the observed image and creates 1,000 users instead. Verify the count before a baseline run to avoid unexpected token costs. The image adds and deletes users periodically, so the count and scenario answers can change.

SQLite is inside the container's writable layer, not the course's `/app/data` mount. No ineffective data volume is declared: stopping retains the container's data, while removing/recreating it creates a fresh synthetic dataset. Change `USERS_NUMBER` in Compose and recreate this exercise's container to change the initial dataset size. This is disposable training infrastructure, not a production deployment.

### All Scenarios With Captured Output

```bash
uv run \
  --with-requirements "$PWD/app_development/t6-grounding/solution/t6_grounding/requirements.txt" \
  --directory app_development/t6-grounding/solution \
  python -u -m t6_grounding.runner --all --batch-size 8 --k 10 --score 0.15 \
  --output-dir "$PWD/app_development/t6-grounding/solution/output"
```

This runs three queries through all four strategies: a name taken from the live dataset, `hiking or painting`, and an absent example email. It also captures the deterministic offline output-validation demonstration. No image inputs or image-generation deployment are required for this user-search exercise.

Each transcript contains the strategy, query, applicable prompts, retrieved IDs/scores or API parameters, generated answer, and per-scenario API/token counts. `summary.json` records all results and selected model names. An unsuccessful scenario stops the batch with a nonzero exit; its partial transcript can remain, but a complete summary is only written after successful completion. Repeating a batch overwrites matching filenames.

The baseline uses three eight-user batches for 24 users, with at most three concurrent chat requests, then optionally compiles the findings. Its default batch size remains the course's 100; `--workers` controls concurrency. Token counts are provider-reported usage, not currency estimates. Cold-start discovery/indexing calls are included, so comparisons are not a controlled benchmark.

### Single Query and Interactive Mode

```bash
uv run \
  --with-requirements "$PWD/app_development/t6-grounding/solution/t6_grounding/requirements.txt" \
  --directory app_development/t6-grounding/solution \
  python -u -m t6_grounding.runner --mode inout \
  --query "Find people who enjoy hiking or painting." --k 10 --score 0.15
```

Modes are `no`, `api`, `vector`, `inout`, or `all`. Omit `--query` and `--all` for interactive mode; enter `exit`, `quit`, or EOF to stop. Each question is independent, with no conversation-history evidence. Omit `--output-dir` to print results without saving them.

`--k` limits retrieved records; `--score` is minimum cosine similarity in `[-1, 1]`, not a probability of correctness. Higher thresholds retain fewer candidates. FAISS uses normalized vectors and inner product; Chroma uses cosine distance converted to similarity. Neither technique guarantees all matching users are retrieved.

The original course entry points remain executable with the same options:

| Strategy | Module after `python -m` | Behavior and Limitation |
| --- | --- | --- |
| Baseline | `t6_grounding.t1.no_grounding` | Loads all permitted records, searches parallel batches, then combines model outputs. No authoritative post-generation validation. |
| API input | `t6_grounding.t2.input_api_based` | Extracts explicit name/surname/email filters, queries live records, then generates an answer. Cannot retrieve by hobbies alone. |
| Vector input | `t6_grounding.t2.input_vector_based` | Embeds permitted records into a real FAISS index. Snapshot stays unchanged during the process; restart to refresh. |
| Input-output | `t6_grounding.t3.in_out_grounding` | Synchronizes biographies in real Chroma, generates hobby-to-ID groups, validates IDs, and fetches current permitted details. Cannot establish name/email conditions from biography-only context. |

Both vector stores are in-memory and rebuilt on restart. Chroma compares biographies before each question and embeds only additions/changes, deleting removed IDs. Unchanged biographies are not re-embedded. Current permitted details are fetched after generation, including when non-biography fields have changed.

The course calls the first strategy "No Grounding," but it still supplies external user records in its prompt. The relevant contrast here is the unvalidated model-processing chain versus targeted retrieval and authoritative output lookup.

### Output-Validation Demonstration

No DIAL configuration or running service is needed for this deterministic example:

```bash
uv run \
  --with-requirements "$PWD/app_development/t6-grounding/solution/t6_grounding/requirements.txt" \
  --directory app_development/t6-grounding/solution \
  python -m t6_grounding.runner --validation-demo \
  --output-dir "$PWD/app_development/t6-grounding/solution/output"
```

The demonstration uses an in-process HTTP test transport: generated ID `1` is accepted once with authoritative details, candidate ID `2` returns 404 and is rejected, and invented ID `999` was not retrieved and is rejected before lookup. This is **offline fault injection**, not a claim that the live model hallucinated those IDs. Non-404 service failures propagate as errors.

### Tests and Static Checks

The complete standalone suite makes no DIAL calls and needs no running user service:

```bash
uv run \
  --with-requirements "$PWD/app_development/t6-grounding/solution/t6_grounding/requirements.txt" \
  --with pytest --directory app_development/t6-grounding/solution \
  python -m pytest -q

uv run --with ruff ruff check app_development/t6-grounding/solution
```

Tests exercise real in-memory FAISS/Chroma stores with deterministic vectors, plus HTTP transports for service/DIAL boundaries. Coverage includes cosine ranking, threshold filtering, empty indexes, additions/deletions/changed biographies, unchanged-index reuse, safe field projection, unknown/deleted/duplicate IDs, authoritative record lookup, service failures, DIAL routes/authentication, model-agnostic payloads, and schema validation.

### Stop the Service

```bash
podman-compose -p t6-grounding \
  -f app_development/t6-grounding/solution/t6_grounding/docker-compose.yml stop
```

Use `down` instead of `stop` to remove the container and its disposable database. If host port 8041 is occupied, resolve the conflict before starting this stack; the solution intentionally targets this fixed localhost endpoint.

## Deliverables and Local Output

- [solution/t6_grounding/grounding.py](solution/t6_grounding/grounding.py): DIAL configuration, safe service access, strict structures, vector indexes, and authoritative output validation.
- [solution/t6_grounding/runner.py](solution/t6_grounding/runner.py): four strategies, batch/interactive CLI, prompts, usage, and output capture.
- [solution/t6_grounding/test_t6_grounding.py](solution/t6_grounding/test_t6_grounding.py): offline behavior and real-vector-store regressions.
- [solution/t6_grounding/docker-compose.yml](solution/t6_grounding/docker-compose.yml): localhost synthetic user service.
- [solution/t6_grounding/requirements.txt](solution/t6_grounding/requirements.txt): shared runtime dependencies.
- Original `t1/`, `t2/`, and `t3/` entry points plus the user-service compatibility client are bundled.

Generated captures live in local `solution/output/`, intentionally **inside the solution** as requested. [.gitignore](.gitignore) excludes them, caches, logs, and local data. The batch produces `no_name.txt`, `api_name.txt`, `vector_name.txt`, `inout_name.txt`, equivalent `*_hobbies.txt` and `*_no_match.txt` captures, `output_validation.txt`, and `summary.json`. The local review also includes `verification.txt` (standalone tests) and `standalone/` (an additional live smoke run). Regenerate scenario files with the commands above; do not force-add them to Git.

## Results / Notes

Verified **2026-10-22**: **22 tests passed** in both the working fork and standalone solution. Ruff and strict OpenSpec validation passed. Review added trailing-dot public-OpenAI hostname rejection, ancestor `.env` precedence, and successful API/batch regressions. Python 3.14 emits one upstream Chroma `asyncio.iscoroutinefunction` deprecation warning; tests still pass.

The live batch started with **24 synthetic users** and used the unchanged configured chat deployment, `DeepSeek-V4-Flash-2026-04-23`. Automatic discovery selected `text-embedding-005`; neither observed deployment name is hard-coded. The batch completed with **30 DIAL calls and 17,416 reported tokens**, including indexing/discovery. The earlier interrupted 1,000-user attempt and separate API connectivity check are not included in those batch totals.

| Scenario | Baseline | API Input | FAISS Input | Chroma Input-Output |
| --- | --- | --- | --- | --- |
| Name from dataset | Found the named user. | One live candidate; answered from that record. | Found the user in ten retrieved candidates. | Empty groups: name cannot be verified from biography-only context. |
| Hiking or painting | Returned three users, omitting one painting match. | Declined: no supported explicit API filter. | Returned four users. | Returned one hiking user and three painting users, with live permitted details. |
| Absent email | No users found. | No matching API records. | No matching users in retrieved context. | Empty groups; no invented record returned. |

The live Chroma queries found no dataset changes during this short batch and reused the index. Add/change/delete handling is demonstrated by deterministic offline tests, not inferred from an unchanged live dataset. The offline validation demo rejects deleted ID `2` and invented ID `999` while deduplicating ID `1`.

Tested runtime versions: HTTPX 0.28.1, python-dotenv 1.2.4, Pydantic 2.13.5, NumPy 2.4.6, FAISS CPU 1.15.1, and Chroma 1.5.9. Requirements permit compatible versions rather than imposing these observed versions.

**Limits:** output grounding verifies retrieved-ID membership, current existence, and authoritative returned fields. It does not prove that a hobby label is semantically correct, guarantee exhaustive search, prevent all prompt injection, or eliminate races after the final lookup. Synthetic data and service churn mean future names, counts, tokens, and answers may differ. Review generated claims against the printed evidence.