import os


class SharedSettings:
    def __init__(self):
        self.qdrant_host = os.environ.get("QDRANT_HOST", os.environ.get("qdrant_host", os.environ.get("QDRANT_CLUSTER_ENDPOINT", os.environ.get("qdrant_cluster_endpoint", ""))))
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY", os.environ.get("qdrant_api_key", None))

        self.embedding_model = os.environ.get("EMBEDDING_MODEL", os.environ.get("embedding_model", "amazon.titan-embed-text-v2:0"))
        self.chat_model = os.environ.get("CHAT_MODEL", os.environ.get("chat_model", "anthropic.claude-3-haiku-20240307-v1:0"))
        self.aws_region = os.environ.get("AWS_REGION", os.environ.get("aws_region", "ap-south-1"))
        self.s3_bucket = os.environ.get("S3_BUCKET", os.environ.get("s3_bucket", "rag-document-store"))
        self.sqs_queue_url = os.environ.get("SQS_QUEUE_URL", os.environ.get("sqs_queue_url", "rag-ingestion-queue"))
        self.qdrant_collection = os.environ.get("QDRANT_COLLECTION", os.environ.get("qdrant_collection", "documents"))


def get_shared_settings() -> SharedSettings:
    return SharedSettings()
