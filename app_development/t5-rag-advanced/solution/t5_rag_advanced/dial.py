import math
import os
from urllib.parse import quote, urlsplit, urlunsplit

import httpx


def dial_root(base_url):
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError(
            "OPENAI_BASE_URL must be an HTTPS DIAL URL without credentials"
        )
    if parsed.hostname == "openai.com" or parsed.hostname.endswith(".openai.com"):
        raise ValueError("Use EPAM DIAL, not a public OpenAI host")
    if parsed.query or parsed.fragment:
        raise ValueError("OPENAI_BASE_URL must not contain a query or fragment")
    path = parsed.path.split("/deployments/", 1)[0].rstrip("/")
    path = path.removesuffix("/chat/completions")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def validate_vectors(vectors):
    if not vectors or not vectors[0]:
        raise ValueError("Empty embedding response")
    dimensions = len(vectors[0])
    for vector in vectors:
        if len(vector) != dimensions or any(
            not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in vector
        ):
            raise ValueError(
                "Embeddings must have consistent dimensions and finite numbers"
            )
        if not any(vector):
            raise ValueError("Zero embeddings cannot be used for cosine search")
    return dimensions


class DialClient:
    def __init__(self, root, model, key, embedding_model, transport=None):
        self.root = dial_root(root)
        self.model = model
        self.embedding_model = embedding_model
        self.key = key
        self.http = transport or httpx.Client(timeout=120)

    @classmethod
    def from_env(cls, embedding_model=None, transport=None):
        names = ("OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY")
        if any(not os.environ.get(name, "").strip() for name in names):
            raise ValueError(
                "Load OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY from root .env"
            )
        client = cls(
            os.environ[names[0]],
            os.environ[names[1]],
            os.environ[names[2]],
            embedding_model,
            transport,
        )
        if not embedding_model:
            payload = client.request("GET", "/models")
            candidates = sorted(
                (
                    item["id"]
                    for item in payload.get("data", [])
                    if "embedding" in item.get("id", "").lower()
                ),
                key=lambda name: (
                    "vision" in name.lower(),
                    not name.lower().startswith("text-embedding"),
                    name,
                ),
            )
            if not candidates:
                client.close()
                raise ValueError(
                    "No embeddings discovered; select --embedding-model <deployment>"
                )
            client.embedding_model = candidates[0]
        return client

    def request(self, method, path, payload=None):
        try:
            response = self.http.request(
                method, self.root + path, headers={"Api-Key": self.key}, json=payload
            )
        except httpx.HTTPError:
            raise RuntimeError(
                "DIAL request failed; check connectivity and configuration"
            ) from None
        if response.is_error:
            raise RuntimeError(
                f"DIAL returned HTTP {response.status_code}; response body omitted"
            )
        return response.json()

    def embed(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            raise ValueError("At least one embedding input is required")
        payload = self.request(
            "POST",
            f"/deployments/{quote(self.embedding_model, safe='')}/embeddings",
            {
                "model": self.embedding_model,
                "input": texts,
            },
        )
        records = payload.get("data", [])
        indices = [record.get("index") for record in records]
        if len(indices) != len(texts) or set(indices) != set(range(len(texts))):
            raise ValueError("Embedding response indices do not match inputs")
        vectors = [
            record["embedding"]
            for record in sorted(records, key=lambda item: item["index"])
        ]
        validate_vectors(vectors)
        return vectors

    def complete(self, messages):
        payload = self.request(
            "POST",
            f"/deployments/{quote(self.model, safe='')}/chat/completions",
            {
                "model": self.model,
                "messages": messages,
            },
        )
        choices = payload.get("choices", [])
        content = choices[0].get("message", {}).get("content") if choices else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("DIAL returned no text answer")
        return content

    def close(self):
        self.http.close()
