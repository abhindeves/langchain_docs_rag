import sys
import types

# Workaround for Ragas crashing on missing ChatVertexAI in new LangChain Community versions
if "langchain_community.chat_models.vertexai" not in sys.modules:
    dummy_module = types.ModuleType("langchain_community.chat_models.vertexai")
    dummy_module.ChatVertexAI = type("ChatVertexAI", (object,), {})  # type: ignore
    sys.modules["langchain_community.chat_models.vertexai"] = dummy_module

import io
import logging
import random

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from config import get_eval_settings  # type: ignore
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas.testset import TestsetGenerator

logger = logging.getLogger(__name__)


def fetch_documents_from_s3(bucket: str, prefix: str, limit: int = 5) -> list[Document]:
    """Fetches a random subset of long text documents from S3."""
    s3_client = boto3.client("s3")
    documents = []

    # 1. Grab all file keys (fast)
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    all_keys = [obj["Key"] for page in pages for obj in page.get("Contents", []) if obj["Key"].endswith(".json")]
    if not all_keys:
        print(f"No documents found in s3://{bucket}/{prefix}")
        return []

    import json

    # 2. Shuffle the keys to guarantee variety
    random.shuffle(all_keys)

    # 3. Only download files until we find `limit` valid (long enough) documents
    for key in all_keys:
        file_obj = s3_client.get_object(Bucket=bucket, Key=key)
        content = file_obj["Body"].read().decode("utf-8")

        try:
            data = json.loads(content)
            if isinstance(data, dict):
                content = data.get("page_content", data.get("text", content))
        except json.JSONDecodeError:
            pass

        # Filter out short/stub documents that crash Ragas
        if len(content.strip()) > 500:
            # Ragas HeadlineSplitter CRASH FIX:
            # If the document has no markdown headers, the LLM fails to extract headlines
            # which crashes the pipeline. We inject a dummy header to guarantee success.
            if "# " not in content:
                content = f"# {key}\n\n{content}"

            documents.append(Document(page_content=content, metadata={"source": f"s3://{bucket}/{key}", "filename": key}))

        if len(documents) >= limit:
            break

    return documents


def generate_incremental_dataset():
    settings = get_eval_settings()
    s3_client = boto3.client("s3", region_name=settings.aws_region)
    dataset_key = "evaluation/golden_dataset.csv"

    print("\n--- 1. CHECKING EXISTING DATASET ---")
    print(f"Checking for existing dataset at s3://{settings.s3_bucket}/{dataset_key}...")
    existing_df = pd.DataFrame()

    try:
        response = s3_client.get_object(Bucket=settings.s3_bucket, Key=dataset_key)
        csv_content = response["Body"].read().decode("utf-8")
        existing_df = pd.read_csv(io.StringIO(csv_content))
        print(f"Found existing dataset with {len(existing_df)} rows.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print("No existing dataset found. Starting fresh.")
        else:
            raise e

    if len(existing_df) >= 75:
        print("🎉 Target of 75 questions reached! Exiting successfully.")
        return

    print("\n--- 2. INITIALIZING GEMINI MODELS ---")
    generator_llm = ChatGoogleGenerativeAI(model=settings.eval_model, google_api_key=settings.gemini_api_key)
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2", google_api_key=settings.gemini_api_key)  # type: ignore

    generator = TestsetGenerator.from_langchain(llm=generator_llm, embedding_model=embeddings)

    print("\n--- 3. SELECTING DOCUMENT SUBSET ---")
    docs_subset = fetch_documents_from_s3(settings.s3_bucket, settings.s3_prefix, limit=5)

    if not docs_subset:
        print("Error: No valid documents found to generate dataset from.")
        return

    print(f"Successfully selected a batch of {len(docs_subset)} sufficiently long documents to guarantee variety.")

    print("\n--- 4. GENERATING TESTSET ---")
    generate_count = min(settings.testset_size, 75 - len(existing_df))
    print(f"Targeting {generate_count} new test cases...")

    new_dfs = []
    successful_generations = 0

    # Process each document individually so a single Ragas crash doesn't kill the batch
    for doc in docs_subset:
        if successful_generations >= generate_count:
            break

        print(f"\nAttempting generation for: {doc.metadata['filename']}")
        try:
            testset = generator.generate_with_langchain_docs([doc], testset_size=1)
            new_dfs.append(testset.to_pandas())  # type: ignore
            successful_generations += 1
            print(f"Successfully generated testcase for {doc.metadata['filename']}")
        except Exception:
            logger.exception("Generation failed for %s", doc.metadata["filename"])

    if not new_dfs:
        raise RuntimeError("Failed to generate any test cases from the selected batch")

    new_df = pd.concat(new_dfs, ignore_index=True)

    print("\n--- 5. UPLOADING INCREMENTAL UPDATE ---")
    print(f"Appending {len(new_df)} new rows...")
    final_df = pd.concat([existing_df, new_df], ignore_index=True)

    print(f"Uploading combined dataset ({len(final_df)} total rows)...")
    csv_buffer = io.StringIO()
    final_df.to_csv(csv_buffer, index=False)

    s3_client.put_object(Bucket=settings.s3_bucket, Key=dataset_key, Body=csv_buffer.getvalue())
    print(f"Successfully uploaded! Dataset now has {len(final_df)} questions.")
    if len(final_df) >= 75:
        print("🎉 Target of 75 questions reached!")


if __name__ == "__main__":
    generate_incremental_dataset()
