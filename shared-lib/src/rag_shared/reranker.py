import asyncio

import boto3

from rag_shared.config import get_shared_settings


class Reranker:
    def __init__(self, region_name: str | None = None):
        settings = get_shared_settings()

        # Use explicitly passed region, or config setting, or default to fallback if ap-south-1
        self.region = region_name or settings.reranker_region or settings.aws_region
        if self.region == "ap-south-1":
            self.region = "us-west-2"

        self.model_arn = f"arn:aws:bedrock:{self.region}::foundation-model/amazon.rerank-v1:0"
        # Boto3 client uses adaptive rate-limiting and retries
        self.client = boto3.client("bedrock-agent-runtime", region_name=self.region)

    def _rerank_sync(self, query: str, documents: list[str], limit: int) -> dict:
        sources = [{"type": "INLINE", "inlineDocumentSource": {"type": "TEXT", "textDocument": {"text": doc}}} for doc in documents]
        return self.client.rerank(
            queries=[{"type": "TEXT", "textQuery": {"text": query}}],
            sources=sources,
            rerankingConfiguration={"type": "BEDROCK_RERANKING_MODEL", "bedrockRerankingConfiguration": {"modelConfiguration": {"modelArn": self.model_arn}, "numberOfResults": limit}},
        )

    async def rerank(self, query: str, results: list[dict], limit: int) -> list[dict]:
        if not results:
            return []

        doc_texts = [r["text"] for r in results]
        response = await asyncio.to_thread(self._rerank_sync, query, doc_texts, limit)

        reranked = []
        for rank in response.get("results", []):
            index = rank["index"]
            original = results[index]
            reranked.append({"chunk_id": original["chunk_id"], "score": rank["relevanceScore"], "text": original["text"], "metadata": original["metadata"]})
        return reranked
