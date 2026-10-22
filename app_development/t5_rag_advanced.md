# RAG Advanced

## Understanding Embeddings

Embeddings are numerical representations of text (or other data) in a high-dimensional vector space where semantic similarities are preserved as geometric relationships.

In simpler terms: embeddings convert text into lists of numbers that capture meaning. Words or phrases with similar meanings will have similar number patterns.

### Vectors and Dimensions

The number of **dimensions** is the number of numerical values in each embedding vector.

Example vector:

```text
[0.243, 0.895803, -0.328932, 0.533, 0.1, ..., 0.7748]
```

| Dimension | Value |
|-----------|-------|
| 1st | 0.243 |
| 2nd | 0.895803 |
| 3rd | -0.328932 |

### How Embeddings Are Created

> **Note:** This information provides a basic understanding of how embedding models work internally during vector generation. This foundational knowledge will help you grasp key concepts covered in the additional task and avoid common misunderstandings when working with embedding models.

```text
Input text → Tokenizer → Embedding lookup → Encoder (Transformer) → Pooling → Normalization → Use
```

#### 1. Input Text

We start generating embeddings with some text:

> I love machine learning.

#### 2. Tokenizer

The tokenizer converts text to subword/byte tokens, often something like:

```text
Input:     "I love machine learning."
Tokens:    ["I", "love", "machine", "learning", "."]
Token IDs: [40, 4682, 903, 723, 11]
```

#### 3. Embedding Lookup

Each token ID maps to a learnable vector from the model's embedding matrix $E$ of size $V \times d$.

Example token vectors for "I love machine learning." (shown after the transformer):

| Token ID | Token | Vector | Dimensions |
|----------|-------|--------|------------|
| 40 | `I` | `[0.23, -0.45, 0.67, ..., 0.12]` | 384 |
| 4682 | `love` | `[-0.12, 0.78, -0.34, ..., 0.89]` | 384 |
| 903 | `machine` | `[0.45, -0.23, 0.91, ..., -0.56]` | 384 |
| 723 | `learning` | `[0.78, 0.34, -0.67, ..., 0.23]` | 384 |
| 11 | `.` | `[-0.09, 0.12, 0.45, ..., -0.78]` | 384 |

> **Read more:** The source mentions "Article 1" and "Article 2", but no URLs were provided.

#### 4. Encoder (Transformer)

The sequence of token vectors passes through multiple self-attention layers (typically 12 layers in BERT-base) to produce contextualized representations.

| Stage | What Happens |
|-------|--------------|
| Initial state | Each token has its basic embedding. |
| After layer 1 | The `love` embedding is influenced by the `I`, `machine`, and `learning` context. |
| After layer 6 | `machine` now strongly associates with `learning`. |
| After layer 12 | `machine` is specialized for the ML context (not physical machines), and `learning` is contextualized for the educational/AI meaning. |

Each token's final embedding captures its meaning within this specific sentence.

**Result:** 5 contextualized token embeddings, still 768 dimensions each, but now context-aware.

#### 5. Pooling

After the transformer layers, you have multiple token embeddings, one for each token in your sentence:

| Token | Vector After Transformer |
|-------|--------------------------|
| `I` | `[0.23, -0.45, 0.67, ..., 0.12]` |
| `love` | `[-0.12, 0.78, -0.34, ..., 0.89]` |
| `machine` | `[0.45, -0.23, 0.91, ..., -0.56]` |
| `learning` | `[0.78, 0.34, -0.67, ..., 0.23]` |
| `.` | `[-0.09, 0.12, 0.45, ..., -0.78]` |

**Pooling** combines multiple token vectors into one sentence vector.

Why do you need one vector? Vector databases and similarity search systems expect:

- Each document/sentence to have exactly one vector.
- All vectors to have the same number of dimensions.
- A single similarity calculation to compare "sentence A" with "sentence B".

Without pooling, you'd have to answer: "How do I compare sentence A (5 vectors) with sentence B (7 vectors)?" It's not clear how to do this efficiently.

#### 6. Normalization

Normalization ensures that similarity scores aren't skewed by vector magnitude. It focuses on the angle between vectors (semantic similarity) rather than their length.

> **Read more:** The source mentions "Article 1" and "Article 2", but no URLs were provided.

#### 7. Use

At this stage, we have the embedding for "I love machine learning." and can save it to the vector database or use it to search the database.

### Embedding Models

| Provider / Category | Model | Dimensions | Notes |
|---------------------|-------|------------|-------|
| OpenAI | `text-embedding-3-small` | Up to 1536 | Cost-effective, good performance |
| OpenAI | `text-embedding-3-large` | Up to 3072 | Highest accuracy; can be reduced to lower dimensions |
| Open source | `sentence-transformers/all-MiniLM-L6-v2` | Up to 384 | Sentence-transformer model |
| Open source | Various Hugging Face transformer models | Varies | Other available models |

## Vector Databases and Storage

A vector database is a specialized storage system optimized for:

- Storing high-dimensional vectors (embeddings)
- Performing fast similarity searches
- Scaling to millions or billions of vectors

**Popular vector databases:** FAISS, ChromaDB, Milvus, pgvector (PostgreSQL extension).

## Data Transformation Pipeline

```text
Raw Data (source) → Load → Transform → Embed → Store → Retrieve
```

1. **Source:** Documents (`.pdf`, `.txt`, `.html`), APIs, databases.
2. **Load:** Extract and clean text content from the source.
3. **Transform:** Split into chunks and preprocess.
4. **Embed:** Generate vector representations.
5. **Store:** Save in a vector database with metadata.
6. **Retrieve:** Perform similarity searches.

### Document Chunking Strategy

Documents are typically split into smaller chunks because:

- LLMs have context length limits.
- Smaller chunks provide more precise retrieval.
- Chunking improves performance for similarity matching.

Common chunking approaches:

- Fixed size (100-500 words)
- Sentence-based boundaries
- Semantic chunking (maintaining topic coherence)

### Sample Data in a Vector Database

| `document_name` | `text` | `embedding` |
|-----------------|--------|-------------|
| `manual.txt` | I love machine learning. | `[0.12, 0.34, ...]` |
| `vector_dbs.txt` | Vector databases are useful. | `[0.56, 0.78, ...]` |

Each column has a specific role:

| Column | Contents |
|--------|----------|
| `document_name` | Metadata identifying the source document; metadata is usually stored in a column named `metadata`. |
| `text` | The text chunks. |
| `embedding` | The embeddings (vectors) of the text chunks. |

## RAG Pipeline

```text
User Input → Retrieval [Embed → Vector Search] → Augmentation → Generation → Response
```

| Stage | Description |
|-------|-------------|
| User input | The original user input. |
| Retrieval: embed | Convert the user input into an embedding. |
| Retrieval: vector search | Search for the top-k most relevant text chunks by comparing the input embedding with chunk embeddings. Search algorithms are described below. |
| Augmentation | Concatenate the retrieved context with the original user input. |
| Generation | Provide the LLM with the augmented prompt for response generation. |
| Response | Return the response from the LLM. |

## Search Algorithms in RAG

### Euclidean Distance (L2 Distance)

Euclidean distance measures the straight-line distance between two vectors in high-dimensional space. It is calculated as:

$$
d(\mathbf{u}, \mathbf{v}) = \sqrt{\sum_{i=1}^{n} (u_i - v_i)^2}
$$

Where $\mathbf{u}$ and $\mathbf{v}$ are the vectors, and $n$ is the dimensionality.

Smaller distances indicate higher similarity between vectors.

In PostgreSQL, use the `<->` operator for Euclidean distance in vector similarity searches:

```sql
SELECT *
FROM your_vector_table
ORDER BY embedding <-> '[0.12, 0.34, ...]'
LIMIT 10;
```

### Cosine Similarity

Cosine similarity measures the cosine of the angle between two vectors, which indicates their orientation rather than magnitude. It is calculated as:

$$
\text{cosine\_similarity}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}
$$

Where $\mathbf{u} \cdot \mathbf{v}$ is the dot product of the vectors, and $\|\mathbf{u}\|$ and $\|\mathbf{v}\|$ are their magnitudes.

Values range from -1 (opposite directions) to 1 (same direction), with higher values indicating greater similarity.

In PostgreSQL, use the `<#>` operator for cosine similarity in vector similarity searches. For example:

```sql
SELECT *
FROM your_vector_table
ORDER BY embedding <#> '[0.12, 0.34, ...]'
LIMIT 10;
```

## Tuning RAG Performance

Many people see vector search in vector databases as mysterious, but let's examine how pgvector (a PostgreSQL extension) actually works. In reality, there's no magic involved. It's simply a `SELECT` query that compares vectors using the algorithms described above.

Reference table:

| `document_name` | `text` | `embedding` |
|-----------------|--------|-------------|
| `manual.txt` | I love machine learning. | `[0.12, 0.34, ...]` |
| `vector_dbs.txt` | Vector databases are useful. | `[0.56, 0.78, ...]` |
| `another_doc.txt` | Advanced RAG techniques. | `[0.91, 0.23, ...]` |
| `yet_another_doc.txt` | Exploring vector search. | `[0.45, 0.67, ...]` |

Example query:

```sql
SELECT text, embedding <-> '[0.23, -0.45, 0.67, ..., 0.12]'::vector AS distance
FROM vectors_table
WHERE embedding <-> '[0.23, -0.45, 0.67, ..., 0.12]'::vector <= {score}
ORDER BY distance
LIMIT {top_k};
```

### Key Parameters

#### `top_k`: Number of Retrieved Documents

- **Low values (1-3):** Focused, specific context.
- **High values (5-10):** Broader context, higher computational cost.
- **Optimal range:** Usually 3-5 for most applications.

#### `score`: Quality Filter for the Example SQL Query

| Maximum Distance | Effect |
|------------------|--------|
| 0.8-0.9 | Include more documents; some may be less relevant. |
| 0.4-0.7 | Balanced relevance. |
| 0.1-0.3 | Only highly relevant documents. |

#### `score_threshold`: Quality Filter for Search Results

Commonly used in code and across many libraries:

| Similarity Threshold | Effect |
|----------------------|--------|
| Low (0.1-0.3) | Include more documents; some may be less relevant. |
| Medium (0.4-0.7) | Balanced relevance. |
| High (0.8-0.9) | Only highly relevant documents. |

## Summary

### Key Takeaways

- **RAG is not magic:** It's standard technology: SQL queries with similarity operators, REST APIs, and proven information retrieval techniques combined with LLMs.
- **Solves knowledge gaps:** Enables LLMs to access current, domain-specific information beyond training data instead of hallucinating outdated responses.
- **Simple implementation:** Standard ETL pipeline: chunk text, generate embeddings via APIs, store in vector databases, retrieve using similarity search.
- **Basic parameter tuning:** Performance optimization through adjusting `top_k`, similarity thresholds, and chunking strategies, with no complex algorithms required.

## Useful Links

- [Transformers with 3Blue1Brown](https://www.youtube.com/watch?v=wgfSDrqYMJ4)
- [What Are Word Embeddings?](https://www.youtube.com/watch?v=wjZofJX0v4M)
- [Embeddings: Explanation from Google](https://developers.google.com/machine-learning/crash-course/embeddings/embedding-space)
- [Dimensionality of Word Embeddings](https://www.baeldung.com/cs/dimensionality-word-embeddings)
- [Transformer Explainer: Interactive Visualization](https://poloclub.github.io/transformer-explainer/)

