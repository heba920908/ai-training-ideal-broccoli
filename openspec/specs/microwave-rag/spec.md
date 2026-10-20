# microwave-rag Specification

## Purpose
Provide inspectable microwave-manual assistance through local FAISS retrieval, context-grounded generation via EPAM DIAL, and uv-run commands that capture actual terminal responses for the T4 course exercise.

## Requirements

### Requirement: Local manual indexing
The system SHALL load and split the course manual and create or reuse a local FAISS index with matching query embeddings.

#### Scenario: First run
- **WHEN** no matching local index exists
- **THEN** the manual is split into chunks, embedded, indexed, and persisted

#### Scenario: Repeated run
- **WHEN** the matching local index exists
- **THEN** it is loaded without embedding the manual again or unpickling document data

### Requirement: Grounded RAG pipeline
The system SHALL retrieve chunks with relevance scores, augment the question with context, and instruct the chat model to answer only from that context.

#### Scenario: Relevant question
- **WHEN** a user submits a microwave question
- **THEN** threshold-filtered chunks and the augmented prompt are printed followed by the generated answer

#### Scenario: Unsupported question
- **WHEN** the retrieved context does not contain the answer
- **THEN** the model is instructed to state that the supplied manual context lacks the answer rather than use outside knowledge

### Requirement: DIAL execution and evidence
The system SHALL provide uv-run-compatible interactive, single-query, and batch execution using the existing OPENAI environment contract without logging the API key.

#### Scenario: Batch evidence
- **WHEN** the documented --all command is piped through tee
- **THEN** all seven course examples run and their terminal responses are captured under the exercise output directory

#### Scenario: Embedding configuration
- **WHEN** --embedding-model is omitted
- **THEN** an embedding deployment is discovered from DIAL model IDs or an actionable configuration error is returned
