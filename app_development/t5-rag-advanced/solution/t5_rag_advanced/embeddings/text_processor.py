import hashlib
import json
from contextlib import closing
from enum import StrEnum
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from t5_rag_advanced.dial import validate_vectors
from t5_rag_advanced.utils.text import chunk_text


class SearchMode(StrEnum):
    EUCLIDIAN_DISTANCE = "euclidean"  # Euclidean distance (<->)
    COSINE_DISTANCE = "cosine"  # Cosine distance (<=>)


def search_settings(mode, min_score):
    if not 0 < min_score <= 1:
        raise ValueError("min_score must be greater than 0 and at most 1")
    if mode == "cosine":
        return "<=>", 1 - min_score
    if mode == "euclidean":
        return "<->", 1 / min_score - 1
    raise ValueError("search_mode must be cosine or euclidean")


class TextProcessor:
    def __init__(self, embeddings_client, db_config):
        self.embeddings_client = embeddings_client
        self.db_config = db_config
        self.metadata = None

    def _get_connection(self):
        return psycopg2.connect(**self.db_config, connect_timeout=10)

    def process_text_file(
        self, file_name, chunk_size=300, overlap=40, dimensions=None, truncate=False
    ):
        path = Path(file_name)
        content = path.read_text(encoding="utf-8")
        chunks = chunk_text(content, chunk_size, overlap)
        if not chunks or not content.strip():
            raise ValueError("Manual is empty")
        identity = {
            "source_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "embedding_model": self.embeddings_client.model_name,
            "endpoint": self.embeddings_client.root,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "format": 1,
        }
        with (
            closing(self._get_connection()) as connection,
            connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS rag_index (id INTEGER PRIMARY KEY CHECK (id = 1), metadata JSONB NOT NULL)"
            )
            cursor.execute("SELECT metadata FROM rag_index WHERE id = 1")
            existing = cursor.fetchone()
            if existing and not truncate:
                metadata = existing[0]
                if metadata["identity"] != identity or (
                    dimensions and dimensions != metadata["dimensions"]
                ):
                    raise ValueError(
                        "Index identity differs; use --reload to replace the local index"
                    )
                cursor.execute("SELECT count(*) FROM vectors")
                count = cursor.fetchone()[0]
                if count != metadata["chunks"]:
                    raise ValueError("Index row count differs; use --reload")
                self.metadata = metadata
                print(f"Reusing {count} chunks, dimensions={metadata['dimensions']}.")
                return count
        vectors = []
        for offset in range(0, len(chunks), 16):
            batch = chunks[offset : offset + 16]
            indexed = self.embeddings_client.get_embeddings(
                batch, dimensions=dimensions
            )
            vectors.extend(indexed[position] for position in range(len(batch)))
        width = validate_vectors(vectors)
        if dimensions is not None and width != dimensions:
            raise ValueError("Embedding dimensions do not match the requested width")
        metadata = {"identity": identity, "dimensions": width, "chunks": len(chunks)}
        with (
            closing(self._get_connection()) as connection,
            connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT pg_advisory_xact_lock(543305)")
            cursor.execute("SELECT metadata FROM rag_index WHERE id = 1")
            current = cursor.fetchone()
            if not truncate and current:
                raise ValueError(
                    "Index changed during load; rerun without --reload to validate it"
                )
            self._truncate_table(cursor, width)
            for chunk, vector in zip(chunks, vectors):
                self._save_chunk(cursor, path.name[:64], chunk, vector)
            cursor.execute("DELETE FROM rag_index")
            cursor.execute(
                "INSERT INTO rag_index (id, metadata) VALUES (1, %s::jsonb)",
                (json.dumps(metadata),),
            )
        self.metadata = metadata
        print(
            f"Indexed {len(chunks)} chunks, dimensions={width} (size={chunk_size}, overlap={overlap})."
        )
        return len(chunks)

    def _truncate_table(self, cursor, dimensions):
        if not 1 <= dimensions <= 16000:
            raise ValueError("Embedding dimensions must be between 1 and 16000")
        cursor.execute("DROP TABLE IF EXISTS vectors")
        cursor.execute(
            sql.SQL(
                "CREATE TABLE vectors (id SERIAL PRIMARY KEY, document_name VARCHAR(64), text TEXT NOT NULL, embedding VECTOR({}) NOT NULL)"
            ).format(sql.Literal(dimensions))
        )

    def _save_chunk(self, cursor, document_name, text, embedding):
        cursor.execute(
            "INSERT INTO vectors (document_name, text, embedding) VALUES (%s, %s, %s::vector)",
            (document_name, text, json.dumps(embedding)),
        )

    def search(
        self,
        user_request,
        search_mode="cosine",
        top_k=5,
        min_score=0.5,
        dimensions=None,
    ):
        operator, maximum_distance = search_settings(search_mode, min_score)
        if top_k < 1:
            raise ValueError("top_k must be positive")
        vector = self.embeddings_client.get_embeddings(
            user_request, dimensions=dimensions
        )[0]
        validate_vectors([vector])
        if self.metadata and len(vector) != self.metadata["dimensions"]:
            raise ValueError(
                "Query embedding dimensions differ from the index; use --reload"
            )
        statement = sql.SQL(
            "SELECT id, text, document_name, embedding {} %s::vector AS distance FROM vectors WHERE embedding {} %s::vector <= %s ORDER BY distance, id LIMIT %s"
        ).format(sql.SQL(operator), sql.SQL(operator))
        encoded = json.dumps(vector)
        with (
            closing(self._get_connection()) as connection,
            connection,
            connection.cursor(cursor_factory=RealDictCursor) as cursor,
        ):
            cursor.execute(statement, (encoded, encoded, maximum_distance, top_k))
            results = [dict(row) for row in cursor.fetchall()]
        for row in results:
            row["score"] = (
                max(0.0, min(1.0, 1 - row["distance"]))
                if search_mode == "cosine"
                else 1 / (1 + row["distance"])
            )
        return results

    def dimension_mismatch(self, query):
        vector = self.embeddings_client.get_embeddings(query)[0] + [0.0]
        with (
            closing(self._get_connection()) as connection,
            connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT embedding <=> %s::vector FROM vectors LIMIT 1",
                (json.dumps(vector),),
            )
            cursor.fetchone()
        raise RuntimeError("Expected pgvector to reject the wrong-width query")

    def export_embeddings(self, destination):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with (
            closing(self._get_connection()) as connection,
            connection,
            connection.cursor(cursor_factory=RealDictCursor) as cursor,
        ):
            cursor.execute(
                "SELECT id, document_name, text, embedding::text AS embedding FROM vectors ORDER BY id"
            )
            rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row["embedding"] = json.loads(row["embedding"])
        path.write_text(
            json.dumps({"metadata": self.metadata, "vectors": rows}), encoding="utf-8"
        )
        print(f"Exported {len(rows)} embeddings to {path.name}.")
