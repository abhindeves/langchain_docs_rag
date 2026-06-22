import json

import boto3

from shared.config import get_shared_settings


class Embedder:
    def __init__(self):
        settings = get_shared_settings()
        self.model_id = settings.embedding_model

        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.aws_region,
        )

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding vector for a single query string using Bedrock."""
        payload = {"inputText": text, "dimensions": 1024, "normalize": True}
        response = self.client.invoke_model(
            body=json.dumps(payload),
            modelId=self.model_id,
            accept="application/json",
            contentType="application/json",
        )
        # response["body"] is a streaming body, we need to read and decode it
        response_body = json.loads(response.get("body").read())
        return response_body.get("embedding")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a list of document strings."""
        if not texts:
            return []
        return [self.embed_query(t) for t in texts]
