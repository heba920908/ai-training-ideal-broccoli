# pgvector-microwave-rag Specification

## Purpose
Provide reproducible, framework-free microwave-manual RAG using DIAL embeddings and configured chat, identity-safe PostgreSQL/pgvector persistence, and ignored local experiment evidence.

## Requirements

### Requirement: Environment-only DIAL adapters
The application SHALL use OPENAI_BASE_URL, OPENAI_MODEL, and OPENAI_API_KEY, reject public OpenAI hosts, and authenticate through Api-Key without additional required model variables.

#### Scenario: Configured chat and text embeddings
- **WHEN** the application starts
- **THEN** chat uses OPENAI_MODEL and text embeddings are discovered through DIAL or selected by CLI

### Requirement: Identity-safe persistence
The application SHALL index the manual transactionally with native vector dimensions and persist source, endpoint, model, and chunk identity.

#### Scenario: Incompatible reuse
- **WHEN** the requested identity differs from stored metadata
- **THEN** reuse fails without modifying the stored index and requests explicit reload

### Requirement: Explainable retrieval and generation
The application SHALL support cosine and Euclidean retrieval, configurable top-k and score thresholds, and context-only generation.

#### Scenario: Course batch
- **WHEN** batch mode runs
- **THEN** all seven course questions print scores, retrieved chunks, augmented prompts, and generated answers

### Requirement: Reproducible local experiments
The solution SHALL bundle Podman Compose, SQL, manual, tests, and instructions and ignore generated output and exports.

#### Scenario: Dimension mismatch
- **WHEN** the mismatch experiment runs
- **THEN** pgvector rejects a wrong-width query without changing indexed data or calling another provider
