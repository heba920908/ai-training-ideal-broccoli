import json
import math
import os
import threading
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, StrictInt


def load_environment():
    for parent in Path(__file__).resolve().parents:
        if (parent / ".env").is_file():
            load_dotenv(parent / ".env", override=False)
            break


def public_user(user):
    return {
        key: user[key]
        for key in ("id", "name", "surname", "email", "about_me")
        if key in user
    }


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hobby: str = Field(min_length=1)
    user_ids: list[StrictInt]


class Groups(BaseModel):
    model_config = ConfigDict(extra="forbid")
    groups: list[Group]


class UserService:
    def __init__(self, base="http://127.0.0.1:8041", http=None):
        parsed = urlsplit(base)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.username
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("User service must be a localhost HTTP URL")
        self.base = base.rstrip("/")
        self.http = http or httpx.Client(timeout=30)

    def get(self, path, params=None):
        try:
            response = self.http.get(self.base + path, params=params)
        except httpx.HTTPError:
            raise RuntimeError("Local user service unavailable") from None
        if response.status_code == 404:
            return None
        if response.is_error:
            raise RuntimeError(
                f"User service HTTP {response.status_code}; body omitted"
            )
        return response.json()

    def all(self):
        return [public_user(user) for user in self.get("/v1/users")]

    def search(self, params):
        return [public_user(user) for user in self.get("/v1/users/search", params)]

    def user(self, user_id):
        user = self.get(f"/v1/users/{user_id}")
        return public_user(user) if user else None

    def close(self):
        self.http.close()


class VectorIndex:
    def __init__(self, dial, backend):
        import numpy as np

        self.np = np
        self.dial, self.backend = dial, backend
        self.records, self.documents, self.vectors = {}, {}, {}
        self.index = None
        if backend == "chroma":
            import chromadb
            from chromadb.config import Settings

            self.client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
            from uuid import uuid4

            self.collection = self.client.create_collection(
                "users-" + uuid4().hex,
                metadata={"hnsw:space": "cosine"},
                embedding_function=None,
            )
        elif backend != "faiss":
            raise ValueError("Vector backend must be faiss or chroma")

    def document(self, user):
        if self.backend == "chroma":
            return json.dumps({"id": user["id"], "about_me": user.get("about_me", "")})
        return json.dumps(public_user(user), sort_keys=True)

    def sync(self, users):
        records = {str(user["id"]): public_user(user) for user in users}
        documents = {user_id: self.document(user) for user_id, user in records.items()}
        changed = [
            user_id
            for user_id, document in documents.items()
            if self.documents.get(user_id) != document
        ]
        vectors = {}
        for offset in range(0, len(changed), 64):
            batch = changed[offset : offset + 64]
            vectors.update(
                zip(
                    batch,
                    self.dial.embed([documents[user_id] for user_id in batch]),
                    strict=True,
                )
            )
        deleted = set(self.records) - set(records)
        if self.backend == "chroma":
            if deleted:
                self.collection.delete(ids=sorted(deleted))
            if changed:
                self.collection.upsert(
                    ids=changed,
                    documents=[documents[user_id] for user_id in changed],
                    embeddings=[vectors[user_id] for user_id in changed],
                )
        self.vectors = {
            user_id: vector
            for user_id, vector in self.vectors.items()
            if user_id in records
        }
        self.vectors.update(vectors)
        self.records, self.documents = records, documents
        if self.backend == "faiss":
            import faiss

            self.ids = list(records)
            self.index = None
            if self.ids:
                matrix = self.np.asarray(
                    [self.vectors[user_id] for user_id in self.ids], dtype="float32"
                )
                faiss.normalize_L2(matrix)
                self.index = faiss.IndexFlatIP(matrix.shape[1])
                self.index.add(matrix)
        print(
            f"Index {self.backend}: {len(records)} users; {len(changed)} embedded, {len(deleted)} deleted"
        )

    def search(self, query, k, threshold):
        if k < 1 or not -1 <= threshold <= 1:
            raise ValueError("k must be positive and score must be between -1 and 1")
        if not self.records:
            return []
        vector = self.dial.embed([query])[0]
        if self.backend == "chroma":
            result = self.collection.query(
                query_embeddings=[vector],
                n_results=min(k, len(self.records)),
                include=["distances"],
            )
            ranked = zip(
                result["ids"][0],
                (1 - distance for distance in result["distances"][0]),
                strict=True,
            )
        else:
            import faiss

            matrix = self.np.asarray([vector], dtype="float32")
            if matrix.shape[1] != self.index.d:
                raise ValueError("Query embedding dimensions differ from index")
            faiss.normalize_L2(matrix)
            scores, indices = self.index.search(matrix, min(k, len(self.records)))
            ranked = (
                (self.ids[int(index)], float(score))
                for index, score in zip(indices[0], scores[0], strict=True)
            )
        return [
            (self.records[user_id], max(-1.0, min(1.0, score)))
            for user_id, score in ranked
            if score >= threshold
        ]


def ground_output(payload, candidate_ids, service):
    parsed = Groups.model_validate(payload)
    result, rejected = {}, set()
    for group in parsed.groups:
        records = result.setdefault(group.hobby, [])
        seen = {user["id"] for user in records}
        for user_id in group.user_ids:
            if user_id in seen:
                continue
            if user_id not in candidate_ids:
                rejected.add(user_id)
                continue
            user = service.user(user_id)
            if user is None:
                rejected.add(user_id)
                continue
            if user.get("id") != user_id:
                raise ValueError("User service returned a mismatched ID")
            records.append(user)
            seen.add(user_id)
    return {hobby: users for hobby, users in result.items() if users}, sorted(rejected)


class Dial:
    def __init__(self, base, model, key, embedding_model=None, http=None):
        parsed = urlsplit(base)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OPENAI_BASE_URL must be an HTTPS DIAL URL without credentials"
            )
        hostname = parsed.hostname.rstrip(".")
        if hostname == "openai.com" or hostname.endswith(".openai.com"):
            raise ValueError("Use EPAM DIAL, not public OpenAI")
        path = parsed.path.split("/deployments/", 1)[0].rstrip("/")
        if not path:
            path = "/openai"
        self.root = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
        self.model, self.key, self.embedding_model = model, key, embedding_model
        self.http = http or httpx.Client(timeout=180)
        self.calls = self.total_tokens = 0
        self.lock = threading.Lock()

    @classmethod
    def from_env(cls, embedding_model=None):
        load_environment()
        names = ("OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY")
        if any(not os.environ.get(name, "").strip() for name in names):
            raise ValueError(
                "Configure OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY in root .env"
            )
        return cls(
            *(os.environ[name] for name in names), embedding_model=embedding_model
        )

    def request(self, method, path, payload=None):
        try:
            response = self.http.request(
                method, self.root + path, headers={"Api-Key": self.key}, json=payload
            )
        except httpx.HTTPError:
            raise RuntimeError("DIAL connection failed; details omitted") from None
        if response.is_error:
            raise RuntimeError(f"DIAL HTTP {response.status_code}; body omitted")
        data = response.json()
        with self.lock:
            self.calls += 1
            self.total_tokens += (data.get("usage") or {}).get("total_tokens", 0)
        return data

    def embed(self, texts):
        if not texts:
            return []
        if not self.embedding_model:
            models = self.request("GET", "/models").get("data", [])
            candidates = sorted(
                (
                    item["id"]
                    for item in models
                    if "embedding" in item.get("id", "").lower()
                ),
                key=lambda name: (
                    "vision" in name.lower(),
                    not name.startswith("text-embedding"),
                    name,
                ),
            )
            if not candidates:
                raise ValueError(
                    "No embedding deployment found; supply --embedding-model"
                )
            self.embedding_model = candidates[0]
        data = self.request(
            "POST",
            f"/deployments/{quote(self.embedding_model, safe='')}/embeddings",
            {"model": self.embedding_model, "input": texts},
        )
        records = data.get("data", [])
        if len(records) != len(texts) or {item.get("index") for item in records} != set(
            range(len(texts))
        ):
            raise ValueError("Embedding indices do not match inputs")
        vectors = [
            item["embedding"]
            for item in sorted(records, key=lambda item: item["index"])
        ]
        width = len(vectors[0])
        if not width or any(
            len(vector) != width
            or not any(vector)
            or any(
                not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in vector
            )
            for vector in vectors
        ):
            raise ValueError("Embeddings must be finite, nonzero and equal-width")
        return vectors

    def complete(self, system, message, schema=None):
        if schema:
            system += "\nReturn only JSON matching this schema: " + json.dumps(
                schema.model_json_schema()
            )
        data = self.request(
            "POST",
            f"/deployments/{quote(self.model, safe='')}/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
            },
        )
        content = data["choices"][0]["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("DIAL returned an empty answer")
        if schema:
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return schema.model_validate_json(text).model_dump()
        return content

    def close(self):
        self.http.close()
