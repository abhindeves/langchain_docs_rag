import asyncio

import boto3
from botocore.config import Config

from rag_shared.config import get_shared_settings


class LLM:
    def __init__(self):
        settings = get_shared_settings()
        self.model = settings.chat_model
        self.region = settings.aws_region

        # Configure Boto3 to use adaptive rate-limiting and retries
        config = Config(
            retries={
                "max_attempts": 5,  # Retry up to 10 times
                "mode": "standard",  # Client-side rate-limiting + backoff
            }
        )

        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.region,
            config=config,
        )

    def _build_message(self, query_text: str, context: str) -> tuple[list[dict], list[dict]]:
        """
        Builds the system and user messages structure for Bedrock Converse API.
        """
        system_message = (
            "You are a helpful assistant answering questions strictly based on the provided document context. "
            "If you do not know the answer based on the context, say that you do not know. Do not make up information."
        )

        user_message_text = f"Context:\n{context}\n\nQuery: {query_text}"

        system = [{"text": system_message}]
        messages = [{"role": "user", "content": [{"text": user_message_text}]}]
        return system, messages

    def _call_bedrock(self, system: list[dict], messages: list[dict]) -> str:
        """
        Performs the synchronous Converse API call to AWS Bedrock.
        """
        response = self.client.converse(
            modelId=self.model,
            messages=messages,
            system=system,
            inferenceConfig={
                "temperature": 0.0,
                "maxTokens": 2048,
            },
        )
        return response["output"]["message"]["content"][0]["text"]

    async def invoke(self, query_text: str, context: str) -> str:
        """
        Asynchronously invokes the LLM with query and context.
        """
        system, messages = self._build_message(query_text, context)
        return await asyncio.to_thread(self._call_bedrock, system, messages)
