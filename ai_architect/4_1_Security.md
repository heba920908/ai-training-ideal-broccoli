# Security

## Core Principles

| Principle | What It Means | Architectural Implication |
| - | - | - |
| Least privilege | Agents and tools get only required access | Scope access by task, user, and data domain |
| Complete mediation | Sensitive actions must be checked outside the model | Keep authorization and policy in code, not prompts |
| Defense in depth | No single guardrail reliably stops prompt attacks | Combine input, retrieval, runtime, and output controls |
| Fail-safe defaults | Uncertain cases should block or escalate | Prefer refusal, redaction, or human review |

Across Wiz, Palo Alto, OWASP, Microsoft, NIST, and CISA/NCSC, the same pattern appears: high-impact decisions must remain outside the model.

That pattern is visible in zero-trust agent guidance ([Microsoft](https://techcommunity.microsoft.com/blog/educatordeveloperblog/zero-trust-agent-architecture-how-to-actually-secure-your-agents/4473995)), OWASP's excessive-agency guidance ([OWASP LLM06](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)), retrieval-first privacy controls ([SD-RAG](https://arxiv.org/html/2601.11199v1)), [NIST AI RMF](https://hyperproof.io/navigating-the-nist-ai-risk%2Dmanagement-framework/) explainers ([Hyperproof](https://hyperproof.io/navigating-the-nist-ai-risk%2Dmanagement-framework/)), and secure-by-default lifecycle guidance (IC3/NCSC joint PDF).

## Reference Framework

| Framework | Best Use | Why It Matters |
| - | - | - |
| [OWASP LLM Top 10](https://owasp.org/www-project-top-ten/) | Runtime and integration risk | Fastest map of deployed LLM failure modes |
| [NIST AI RMF](https://hyperproof.io/navigating-the-nist-ai-risk%2Dmanagement-framework/) | Governance and risk | Organizes work as Govern, Map, Measure, Manage |
| [MITRE ATLAS](https://atlas.mitre.org/matrices/ATLAS) | Adversary behavior | Maps realistic AI attack paths for red teaming |
| [CISA/NCSC Secure AI Development](https://www.cisa.gov/news-events/alerts/2023/11/26/cisa-and-uk-ncsc-unveil-joint-guidelines-secure-ai-system-development) | Lifecycle controls | Covers secure design, build, deploy, and operation |

Use OWASP LLM Top 10 for vulnerabilities, MITRE ATLAS for attacker paths, and NIST AI RMF plus CISA/NCSC guidance for governance. For implementation detail, Cisco's AI security reference architecture is a useful companion.

## OWASP Top 10 for LLM Applications

The 2025 discussion is shaped by the industry's move from simple chatbots to RAG and agents ([Giskard overview](https://www.giskard.ai/knowledge/owasp-top-10-for-llm-2025-understanding-the-risks-of-large-language-models)).

| Risk | Why It Matters | Mitigation Tactics | Sample OSS Solutions |
| - | - | - | - |
| LLM01 Prompt Injection | Untrusted text changes model behavior | Use a strict prompt schema with immutable system blocks; strip or escape instructions from retrieved content before insertion; run a secondary classifier to block jailbreak patterns; deny tool execution unless a policy engine approves intent and user scope | [NVIDIA-NeMo/Guardrails](https://github.com/NVIDIA-NeMo/Guardrails) for prompt guardrails; [protectai/llm-guard](https://github.com/protectai/llm-guard) for prompt and output scanners |
| LLM02 Sensitive Information Disclosure | Context may expose secrets or PII | Apply DLP scanning on prompts and responses for PII and secrets; tokenize or mask sensitive fields before model input; enforce per-tenant context isolation; block responses that match secret patterns (keys, tokens, account IDs) | [microsoft/presidio](https://github.com/microsoft/presidio) for PII detection and redaction; [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets) for secret pattern blocking |
| LLM03 Supply Chain | Models, tools, and data add hidden risk | Pin model, dataset, and plugin versions with checksums; verify signatures for model artifacts in CI or CD; maintain and review an AI BOM per release; gate deployment on vulnerability and license policy checks | [aquasecurity/trivy](https://github.com/aquasecurity/trivy) for image, dependency, and misconfiguration scanning; [DependencyTrack/dependency-track](https://github.com/DependencyTrack/dependency-track) for SBOM and component risk tracking |
| LLM04 Data and Model Poisoning | Bad data can shift behavior at scale | Require source allowlists and signed ingest pipelines; run content integrity checks and anomaly scoring on new corpus chunks; quarantine low-trust documents until review; retrain or reindex only from approved snapshots | [cleanlab/cleanlab](https://github.com/cleanlab/cleanlab) for data quality and anomaly checks; [treeverse/dvc](https://github.com/treeverse/dvc) for signed and versioned data and model pipelines |
| LLM05 Improper Output Handling | Output may become unsafe code or API input | Treat model output as untrusted input; enforce JSON or schema validation before passing to APIs; parameterize SQL, OS, and API calls and block raw command execution; sanitize HTML or Markdown before rendering | [pydantic/pydantic](https://github.com/pydantic/pydantic) for strict schema validation before API calls; [ajv-validator/ajv](https://github.com/ajv-validator/ajv) for JSON Schema enforcement |
| LLM06 Excessive Agency | Agents can take damaging actions | Assign least-privilege OAuth scopes per tool; implement step-up approval for money movement, admin actions, and external communications; enforce max actions per task and hard stop conditions; require deterministic policy checks before every tool call | [open-policy-agent/opa](https://github.com/open-policy-agent/opa) for deterministic policy decisions; [openfga/openfga](https://github.com/openfga/openfga) for fine-grained authorization checks |
| LLM07 System Prompt Leakage | Hidden instructions may be exposed | Store secrets in vaults and never in prompts; split policy text from prompt text and fetch at runtime; add output filters for prompt-extraction patterns; rotate and invalidate leaked prompt templates quickly | [hashicorp/vault](https://github.com/hashicorp/vault) for externalized secret storage; [trufflesecurity/trufflehog](https://github.com/trufflesecurity/trufflehog) for prompt or config secret leak detection |
| LLM08 Vector and Embedding Weaknesses | RAG can cross trust boundaries | Enforce metadata RBAC or ABAC filters before vector search; isolate tenant indexes or namespaces; sign and version embeddings to detect tampering; monitor similarity outliers and unusual cross-tenant hits | [openfga/openfga](https://github.com/openfga/openfga) for pre-retrieval RBAC or ABAC filtering; [qdrant/qdrant](https://github.com/qdrant/qdrant) for payload filters and namespace isolation in vector search |
| LLM09 Misinformation | Confident false answers create business risk | Require retrieval-grounded answers with mandatory citations; set confidence thresholds and auto-refuse below threshold; run factuality checks against trusted sources before final response; route high-risk topics to human review | [deepset-ai/haystack](https://github.com/deepset-ai/haystack) for retrieval-grounded pipelines with citations; [guardrails-ai/guardrails](https://github.com/guardrails-ai/guardrails) for response validation and policy checks |
| LLM10 Unbounded Consumption | Loops and large contexts create cost or denial-of-wallet risk | Set per-user, token, and time budgets at gateway level; enforce request rate limits and concurrency caps; cap context window and tool-loop depth with timeouts; alert and auto-throttle anomalous cost spikes | [Kong/kong](https://github.com/Kong/kong) for gateway rate limits and quotas; [envoyproxy/ratelimit](https://github.com/envoyproxy/ratelimit) for centralized rate limiting |

Prompt injection is often the entry point; weak retrieval controls and excessive tool access usually determine the business impact. The mitigation guidance is consistent across [AppSecWarrior](https://medium.com/@appsecwarrior/breaking-down-owasp-top-10-llm-2025-cd99ed46761b), [Barracuda](https://blog.barracuda.com/2024/11/20/owasp-top-10-risks-large-language-models-2025-updates), [Giskard](https://www.giskard.ai/knowledge/owasp-top-10-for-llm-2025-understanding-the-risks-of-large-language-models), and the specific OWASP guidance for [excessive agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).

## Where control sit in a Real AI Architecture

1. Inputs and external content: sanitize, classify, and treat as untrusted.
2. Retrieval: enforce access control before search, filtered by tenant, role, and provenance.
3. Generation: keep prompts minimal, avoid secrets, and constrain output format.
4. Tools and actions: authorize in deterministic code rather than inside the model.
5. Monitoring: log prompts, retrieval decisions, tool calls, and anomalies for investigation and red teaming.

This is where STRIDE and [MITRE ATLAS](https://atlas.mitre.org/matrices/ATLAS) are most useful: they force control placement by component and attack path. For retrieval abuse and agentic RAG scenarios, [DeepTeam's guide](https://www.trydeepteam.com/guides/guide-red-teaming-agentic-rag) pairs well with [Vectra's ATLAS summary](https://www.vectra.ai/topics/mitre-atlas).

## Zero-Trust for Agents

This becomes an operational problem once assistants can act on behalf of users; prompt injection case studies from Vectra and [RedFox Security](https://www.redfoxsec.com/blog/prompt-injection-in-production-real-world-case-studies-from-llm-deployments) show why.

Apply four rules:
1. Give each agent its own identity.
2. Scope each tool to the minimum necessary function.
3. Enforce policy outside the prompt.
4. Require human approval for destructive, financial, external, or privileged actions.

The model plans; the platform authorizes. That control split is clearest in [Microsoft's zero-trust agent architecture](https://techcommunity.microsoft.com/blog/educatordeveloperblog/zero-trust-agent-architecture-how-to-actually-secure-your-agents/4473995), while identity binding and human-consent controls are reinforced in this [AI trust paper](https://www.preprints.org/manuscript/202602.0085).

## RAG Security: Protect Retrieval Before Generation

RAG security is not only a relevance problem. It is an access-control and integrity problem. The SD-RAG lesson is simple: apply disclosure control before generation [(SD-RAG paper)](https://arxiv.org/html/2601.11199v1).

1. Retrieve only what the current user is allowed to see.
2. Redact sensitive fragments before they reach the model.
3. Verify source provenance so poisoned content does not dominate answers.

That same concern appears in practical testing guidance for agentic RAG systems ([DeepTeam](https://www.trydeepteam.com/guides/guide-red-teaming-agentic-rag)).

## Secure AI Lifecycle

The lifecycle framing aligns the [CISA guidance page](https://www.cisa.gov/resources-tools/resources/guidelines-secure-ai-system-development), the joint [IC3/NCSC PDF](https://www.ic3.gov/CSA/2023/231128.pdf), and [MITRE's ATLAS overview deck](https://csrc.nist.gov/csrc/media/Presentations/2025/mitre-atlas/TuePM2.1-MITRE%20ATLAS%20Overview%20Sept%202025.pdf).

| Lifecycle Stage | What Architects Should Ensure |
|----------------|-------------------------------|
| Secure design | Threat model prompts, retrieval, memory, and tools |
| Secure development | Validate dependencies, datasets, prompts, and model settings |
| Secure deployment | Enforce IAM, segmentation, quotas, secrets management, and approvals |
| Secure operation | Monitor behavior, red-team continuously, and feed findings back |

[NIST AI RMF](https://hyperproof.io/navigating-the-nist-ai-risk%2Dmanagement-framework/) is useful because it keeps security tied to governance and measurable risk, while [Cisco's reference architecture](https://www.cisco.com/site/us/en/learn/topics/artificial-intelligence/ai-security-reference-architecture.html) helps translate that into platform controls.

## Red Teaming

Minimum test set:
1. Direct and indirect prompt injection.
2. RAG poisoning and cross-context retrieval.
3. System prompt leakage.
4. Excessive agency and tool misuse.
5. Hallucination in high-stakes workflows.

OWASP's GenAI Red Teaming Guide is a practical starting point. Practical testing playbooks from [Promptfoo](https://www.promptfoo.dev/blog/owasp-red-teaming/) and [DeepTeam](https://www.trydeepteam.com/guides/guide-red-teaming-agentic-rag) are useful operational complements, while [Schellman](https://www.schellman.com/services/penetration-testing/ai-red-teaming) and [RedFox's MITRE vs OWASP comparison](https://www.redfoxsec.com/blog/mitre-atlas-vs-owasp-llm-top-10-which-framework-should-you-use-in-2026) help frame assessment scope.

## Conclusion

The architect's job is to make trust explicit, actions mediated, and failures containable. For enterprise GenAI, the baseline is clear: least privilege, retrieval controls before generation, policy enforcement outside the model, and continuous monitoring plus red teaming. That shift from perimeter thinking to continuous verification is also echoed in [Vectra's prompt injection](https://www.vectra.ai/topics/prompt-injection) overview, [Promptfoo's red-teaming guidance](https://www.promptfoo.dev/blog/owasp-red-teaming/), and the retrieval-first logic of [SD-RAG](https://arxiv.org/html/2601.11199v1).

