import asyncio
import json

import boto3
from botocore.config import Config

from shared.config import get_shared_settings


class Embedder:
    def __init__(self):
        settings = get_shared_settings()
        self.model_id = settings.embedding_model

        # Configure Boto3 to use adaptive rate-limiting and retries
        config = Config(
            retries={
                "max_attempts": 10,  # Retry up to 10 times
                "mode": "adaptive",  # Client-side rate-limiting + backoff
            }
        )

        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.aws_region,
            config=config,
        )

    def _embed_query_sync(self, text: str) -> list[float]:
        """Synchronous worker that performs the actual blocking API call."""
        payload = {"inputText": text, "dimensions": 1024, "normalize": True}
        response = self.client.invoke_model(
            body=json.dumps(payload),
            modelId=self.model_id,
            accept="application/json",
            contentType="application/json",
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("embedding")

    async def embed_query(self, text: str) -> list[float]:
        """Async generate embedding vector."""
        return await asyncio.to_thread(self._embed_query_sync, text)

    async def embed_documents(
        self, texts: list[str], concurrency_limit: int = 10
    ) -> list[list[float]]:
        """Async generate embedding vectors for a list of strings in parallel."""
        if not texts:
            return []

        semaphore = asyncio.Semaphore(concurrency_limit)

        async def embed_with_sem(t: str) -> list[float]:
            async with semaphore:
                return await self.embed_query(t)

        tasks = [embed_with_sem(t) for t in texts]

        return await asyncio.gather(*tasks)
