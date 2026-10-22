class ChatCompletionClient:
    def __init__(self, dial_client):
        self.client = dial_client

    def get_completion(self, messages: list[dict]) -> str:
        return self.client.complete(messages)
