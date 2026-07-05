import os


class SharedSettings:
    def __init__(self):
        self.qdrant_host = os.environ.get("QDRANT_HOST", os.environ.get("QDRANT_CLUSTER_ENDPOINT", ""))
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY", None)

        self.embedding_model = os.environ.get("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
        self.chat_model = os.environ.get("CHAT_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
        self.aws_region = os.environ.get("AWS_REGION", "ap-south-1")
        self.s3_bucket = os.environ.get("S3_BUCKET", "rag-document-store")
        self.sqs_queue_url = os.environ.get("SQS_QUEUE_URL", "rag-ingestion-queue")
        self.qdrant_collection = os.environ.get("QDRANT_COLLECTION", "documents")


def get_shared_settings() -> SharedSettings:
    return SharedSettings()
