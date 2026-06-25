"""
Document parsing module for downloading and extracting clean text from HTML,
PDF, and text files.
"""

import urllib.request

import boto3
from langchain_core.documents import Document

from rag_shared.config import get_shared_settings

LLMS_FULL_URL = "https://docs.langchain.com/llms-full.txt"

# Initialize AWS clients
s3_client = boto3.client("s3")
settings = get_shared_settings()


def download_from_s3(bucket: str, key: str) -> str:
    """
    Downloads raw document file contents from the SQS message S3 coordinates.

    Args:
        bucket (str): S3 bucket name.
        key (str): S3 object key path.

    Returns:
        str: Raw decoded text content.
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


def download_raw_docs(url: str = LLMS_FULL_URL) -> str:
    """
    Download raw text content from the target URL with a simple 3-attempt retry.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req) as response:
                return response.read().decode("utf-8")
        except Exception as e:
            if attempt == 2:
                raise e
    raise RuntimeError("Failed to download raw docs")


def parse_raw_docs(raw_content: str) -> list[Document]:
    """
    Parse raw text file contents and convert pages into LangChain Documents.
    """
    lines = raw_content.splitlines()

    doc_starts = []

    for i, line in enumerate(lines):
        if line.startswith("# "):
            j = i + 1

            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines) and lines[j].startswith("Source: "):
                url = lines[j].replace("Source: ", "").strip()
                doc_starts.append((i, j, url))

    documents = []

    for idx, (title_idx, _, url) in enumerate(doc_starts):
        end_idx = doc_starts[idx + 1][0] if idx + 1 < len(doc_starts) else len(lines)

        doc_text = "\n".join(lines[title_idx:end_idx]).strip()

        title = lines[title_idx].replace("# ", "").strip()

        documents.append(
            Document(
                page_content=doc_text,
                metadata={
                    "title": title,
                    "url": url,
                    "source": url,
                },
            )
        )

    print(f"Loaded {len(documents)} documents")
    return documents
