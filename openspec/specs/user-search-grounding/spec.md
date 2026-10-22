# user-search-grounding Specification

## Purpose
Demonstrate and compare four user-search grounding strategies through EPAM DIAL, including authoritative output lookup, incremental vector-index refresh, secret-safe scenario evidence, and standalone course deliverables.

## Requirements

### Requirement: DIAL configuration
The solution SHALL load the root `.env` without overriding exported variables, use the three existing OPENAI variables, reject public OpenAI hosts, and keep keys out of errors and output.

#### Scenario: Deployment configuration
- **WHEN** a DIAL deployment URL and model are configured
- **THEN** requests use DIAL deployment routes with Api-Key authentication and no hard-coded model-specific generation settings.

### Requirement: Four comparative strategies
The solution SHALL implement batch baseline search, structured API field extraction, FAISS semantic input retrieval, and synchronized Chroma input-output grounding.

#### Scenario: Grounded output
- **WHEN** generation proposes unknown, duplicate, or deleted IDs
- **THEN** unknown and deleted IDs are rejected, duplicates are removed, and accepted record fields come from live service lookup.

#### Scenario: Index refresh
- **WHEN** users are added, removed, or their biographies change
- **THEN** the Chroma index reflects those changes before retrieval.

### Requirement: Reproducible deliverables
The solution SHALL include standalone run instructions, offline tests, and ignored output captures for matches, no matches, and validation scenarios.

#### Scenario: Secret-safe evidence
- **WHEN** scenarios are captured
- **THEN** logs exclude credentials and synthetic payment fields and distinguish observed behavior from guarantees.
