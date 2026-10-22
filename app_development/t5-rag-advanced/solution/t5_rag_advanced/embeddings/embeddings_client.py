from t5_rag_advanced.dial import validate_vectors


class EmbeddingsClient:
    def __init__(self, dial_client):
        self.client = dial_client
        self.model_name = dial_client.embedding_model
        self.root = dial_client.root

    def get_embeddings(
        self,
        inputs: str | list[str],
        dimensions: int | None = None,
        print_response: bool = False,
    ) -> dict[int, list[float]]:
        """
        Generate dict of indexed embeddings:
            inputs[0](text) -> [0][embedding]
            inputs[1](text) -> [1][embedding]
            ...

        Args:
            inputs: input text, can be singular string or list of strings
            dimensions: number of dimensions
            print_response: to print response in chat or not
        """
        vectors = self.client.embed(inputs)
        width = validate_vectors(vectors)
        if dimensions is not None and width != dimensions:
            raise ValueError(
                "Requested dimensions differ from the deployment's native width"
            )
        if print_response:
            print(f"Generated {len(vectors)} embeddings, dimensions={width}.")
        return dict(enumerate(vectors))
