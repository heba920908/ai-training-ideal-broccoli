# Agentic AI

Most AI systems wait for a question and return an answer. Agentic AI works differently — it receives a goal, figures out the steps, uses tools to act, remembers what it learned, and keeps going until the job is done.

Teams adopting agentic workflows report 60–80% time savings on repetitive processes, 90% fewer manual errors, and systems that operate 24/7 without constant supervision. The architecture behind those results is what this module is abo

## Foundations

### Four Pillars
An agent is defined by four properties: Autonomy (acts without constant instruction), Reactivity (responds to its environment), Proactivity (pursues goals, not just reactions), Social Ability (coordinates with other agents or humans).

### PPALE Lifecycle
The agent's operating cycle: Perceive → Plan → Act → Learn → Evaluate. Each iteration refines the agent's understanding and improves future decisions.

### ReAct Pattern
The core reasoning loop: Think → Act → Observe, repeated until the goal is reached or a stopping condition is hit. ReAct makes agent behavior transparent and debuggable — you can follow exactly why each action was taken.

### Agentic Loop
The full execution flow: Input → Context Assembly → ReAct Loop → Output, with controls for max iterations, stopping  conditions, and escalation paths to prevent runaway execution.

[part_1_foundations.html](./artifacts/part1_foundations.html)

## Components
  
Every agent is built from four components — Tools, Memory, Context, and Planning. This section covers what each one does, how they connect, and where architects most commonly go wrong when configuring them. Getting these right determines whether your agent is capable and cost-efficient, or expensive and brittle.
### Tools
The agent's hands. Tools fall into four categories: Retrieval, Communication, Data Manipulation, and System Integration. Design each tool with a clear schema, error handling, idempotency, and auth. Start with 3–5 tools — a single agent with 50+ tools becomes unmanageable.
### Memory
Short-term (4K–200K tokens) holds the current conversation and task context. Long-term stores Episodic (past events), Semantic (facts), and Procedural (how-to) knowledge. Retrieval combines semantic search, temporal recency, and contextual relevance. Architecture: Hot/Warm/Cold storage tiers, vector + BM25 hybrid search, PII handling.
### Context
The window the agent reasons within (128K–200K tokens). Assembled from: System prompt + Memory + Task + Conversation. When it fills up, compress via summarization, chunking, pruning, or caching. The key trade-off: more context improves decisions but increases latency and cost.
### Planning
Reactive planning handles immediate, single-step actions. Proactive anticipates future needs. Hierarchical decomposes complex goals into sub-tasks. Shallow planning is fast; deep planning is more optimal — choose based on your latency budget.
### System Prompt
The agent's constitution. Structure it with six sections: ROLE, GOALS, TOOLS, REFLECTION, ESCALATION, CONSTRAINTS. Unlike a chatbot prompt, it must encode autonomy boundaries, multi-step behavior, and learning triggers.
### Common Pitfalls
* Swiss Army Knife: one agent, 50+ tools — specialise instead
* Memory overflow: loading everything into context — retrieve selectively
* Tool proliferation: adding tools preemptively — add when needed
* Planning paralysis: over-analysing before acting — set iteration limits

[slide04_memory_context.html](./artifacts/slide04_memory_context.html)

## Orchestration

A single agent hits a complexity ceiling. Orchestration is how you coordinate multiple agents to handle tasks that are too large, too parallel, or too specialised for one agent alone. This section covers the five coordination patterns, how agents communicate, and the trade-offs you'll face in production.

### Orchestration Patterns
Orchestration Patterns
Single agent — Focused tasks (<10 tools). Sequential — Pipeline with clear step dependencies. Hierarchical — Supervisor delegates to specialists, validates output. Peer-to-Peer — Agents collaborate dynamically, no central authority. Market-based — Agents bid for tasks based on capacity and expertise.
### Multi-agent Communication
Agents share information through two primary approaches: message passing (explicit requests/responses, including event-driven pub/sub variants) and shared state (common data store).
Coordination can be centralised (one orchestrator) or decentralised (agents negotiate directly). Conflicts resolved by priority rules, voting, or escalation.
### Key Trade-Offs
* Single vs Multi-agent: simplicity vs specialisation
* Sync vs Async: predictability vs throughput
* Tight vs Loose coupling: speed vs resilience
* All multi-agent systems require distributed tracing to debug

[slide06_message_passing.html](./artifacts/slide06_message_passing.html)

## Architecture Decisions

Knowing the patterns isn't enough — you need to choose the right one for a given context. This section covers the judgment calls that separate a demo from a production system: how much autonomy to grant, how to handle non-determinism, and how to meet reliability, cost, and compliance requirements at scale.
### Autonomy Spectrum
Autonomy Spectrum
Four levels from fully autonomous to human-driven. The right level is determined by Risk × Impact: high-stakes or regulated decisions require human approval; routine, low-risk tasks can run fully autonomously. Regulatory constraints (GDPR, finance, healthcare) often set a hard ceiling.
### Key Trade-Offs
* Autonomy vs Control: speed of execution vs oversight and accountability
* Memory vs Performance: richer context vs higher latency/cost. 
* Planning Depth vs Speed: more optimal decisions vs faster response. 
* Accuracy vs Speed: validation steps vs responsiveness. 
* Cost vs Capability: larger models vs routing, caching, compression.

### Production Reliability
Demo systems hide the hard problems: edge cases, cascading errors, and cost at scale. In production: use temperature=0 plus output validation to reduce non-determinism; implement circuit breakers and fallbacks for error handling; separate test and prod environments; instrument with AgentOps, LangSmith, or custom dashboards.
### Scale and Performance
Define latency budgets upfront: chatbot interactions under 2s, workflows under 5 minutes, batch jobs under 1 hour. Manage throughput with throttling, queuing, and multi-provider routing. Reduce cost through prompt caching, result caching, batching, and early stopping.
### Security and Governance 
Enforce least-privilege access with RBAC. Detect and handle PII at ingestion. Log every agent decision, tool call, and outcome for audit. Apply input validation and output filtering as guardrails. Define escalation triggers so agents hand off to humans rather than failing silently.

[part4_architecture.html](./artifacts/part4_architecture.html)

