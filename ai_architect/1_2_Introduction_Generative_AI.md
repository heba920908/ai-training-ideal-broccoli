# Introduction to Generative AI for Architects

## What is IA

Although AI has only relatively recently become mainstream, the term “artificial intelligence” was coined decades ago, and today there are a variety of definitions for it.

> Artificial intelligence is the capacity of a machine to imitate intelligent human behavior.

> Highly autonomous systems that outperform humans at most economically valuable work.

There are three main types of artificial intelligence: NAI, AGI, ASI.

- **Narrow AI (NAI).** Narrow AI, also known as Weak AI, is designed to perform a specific task or a set of tasks. These systems operate under limited contexts and don't possess the ability to generalize their learned knowledge to unfamiliar tasks beyond their predefined programming. Examples of Narrow AI include chatbots, recommendation systems, and image recognition software. The primary characteristic of Narrow AI is its focus on specific, well-defined tasks, and it lacks the broader understanding or adaptability that would enable it to function beyond its specific programmed area.
- **Artificial General Intelligence (AGI).** AGI represents a type of AI that can understand, learn, and apply intelligence across a broad range of tasks, mimicking human intelligence. The key feature of AGI is its flexibility and adaptability: an AGI can perform any intellectual task that a human being can, using the same general abilities. AGI has not yet been achieved but is a major goal in some AI research fields. AGI would be capable of reasoning, problem-solving, and abstract thinking across diverse domains, unlike Narrow AI which is restricted to particular tasks.
- **Artificial Superintelligence (ASI).** ASI refers to a hypothetical AI that surpasses human intelligence across all fields, including creativity, general wisdom, and problem-solving. ASI would not only replicate the multi-faceted intelligence of human beings but would do so at a level higher than the best human brains in practically every field, including scientific creativity, general wisdom, and social skills. The development of ASI could lead to scenarios where AI can improve itself autonomously, potentially leading to rapid advancements beyond human control or understanding.



AI is everywhere and continues expanding. You can read about real-world Generative AI use cases from the world's leading organizations here:

[101 Real-World Generative AI Use Cases from Industry Leaders](https://cloud.google.com/transform/101-real-world-generative-ai-use-cases-from-industry-leaders)

## LLM Architecture styles

From the architectural standpoint, solutions (or solution types) using LLM can be viewed as layers in a pyramid. The depth of each layer reflects both the complexity of the solution and the range of problems it can address.

At the bottom are the most frequent problems and simplest implementations, while the top layer contains the most sophisticated solutions that leverage the full power of large language models.

The simplest of these is a Question‑Answering system. It’s easy to build and can be powered by any LLM – or even a SLM – to answer general queries or domain‑specific questions.

At the other end of the spectrum lies the LLM OS, the most complex and capable solution. It can solve far more problems than a basic QA system, but designing and deploying such an architecture is a significant undertaking that not every organization is prepared for.

```plantuml
@startuml
Piramid that represents LLM architecture styles
Top -> "LLM OS"
Middle -> "RAG; Agents"
Middle -> "Chat bots"
Bottom -> "Question-Answering Systems"
@enduml
```

## AI Risks and challenges

While AI offers significant potential for business growth and innovation, like any emerging technology, it also presents substantial risks and introduces new challenges.

### Ethical Problems
There are several types of ethical problems associated with AI.

#### Job Displacement
AI and automation can lead to significant disruptions in the labor market, with machines replacing human jobs, leading to economic and social strain.

#### Surveillance and Privacy
The use of AI in surveillance technologies can lead to infringements on privacy, raising concerns about the extent to which monitoring should be ethically acceptable.

#### Safety and Security
AI systems can be used to enhance security but also pose risks if they are used in autonomous weapons or if they are hacked.

#### Ethical Alignment
There is a growing concern about whether AI systems can align with complex human values, especially in life-and-death scenarios, as depicted in discussions about autonomous vehicles.

Efforts to address these ethical concerns include the development of AI ethics guidelines by governmental and non-governmental organizations, ethical AI frameworks by industry leaders, and ongoing research into AI governance. Transparency, public engagement, and interdisciplinary collaboration are crucial for addressing the ethical challenges AI poses.
### Security Risks
Security problems associated with AI systems are a critical concern, particularly as these technologies become increasingly embedded in various aspects of daily life and critical infrastructure. One of the primary security issues is the vulnerability of AI systems to adversarial attacks. These are techniques employed by attackers to fool AI models through subtle, often imperceptible, alterations to data that lead the AI to make incorrect decisions. 

For example, slight modifications to an image could cause an AI-driven security system to misidentify a stop sign as a yield sign, potentially causing accidents. This type of vulnerability underscores the need for robust AI security measures to ensure that these systems can resist and recover from such attacks.
### Privacy Concerns
Privacy concerns related to AI are multifaceted, but a particularly alarming issue is the potential for AI to be used to impersonate individuals. This capability raises significant privacy and security concerns, especially when used maliciously. 
For instance, AI-driven deepfake technologies can create convincing video and audio recordings of individuals saying or doing things they never actually said or did. This technology poses a profound threat to personal and professional reputations and can be used to spread misinformation or conduct fraudulent activities.

### Lack of Transparency
The "black box" nature of AI refers to the opacity of many AI systems, particularly those based on deep learning, where even the designers cannot always explain why the AI made a certain decision. This lack of transparency can pose a significant problem for several reasons.
Transparency in AI systems is crucial for trust and accountability. In sectors such as healthcare, finance, and criminal justice, where AI decisions can have profound impacts on human lives, understanding how decisions are made is essential for trust.
### Bias and Fairness
Bias occurs when an AI system displays prejudiced outcomes due to flawed assumptions in the learning algorithm or bias in the training data. 
For instance, if an AI is trained on historical hiring data that reflects a gender imbalance in certain roles, it may continue to favor one gender over another, perpetuating existing inequalities.

## Guide to LLM for SA

When designing and implementing solutions that harness large language models, AI platforms, and AI frameworks, architects should thoughtfully blend deterministic and non‑deterministic techniques to meet business objectives. A deep grasp of how LLMs work, are built and trained is essential for creating cost‑efficient architectures that truly fit the intended purpose.

[llm_architecture-en.html](./artifacts/llm_architecture-en.html)


