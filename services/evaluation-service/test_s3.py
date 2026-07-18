import boto3
from langchain_core.documents import Document
from src.config import get_eval_settings


def fetch_documents_from_s3(bucket: str, prefix: str) -> list[Document]:
    """Fetches text documents from S3 and returns them as LangChain Documents."""
    s3_client = boto3.client("s3")
    documents = []

    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if "Contents" not in response:
        print(f"No documents found in s3://{bucket}/{prefix}")
        return []

    import json

    for obj in response["Contents"]:
        key = obj["Key"]
        if key.endswith(".md") or key.endswith(".txt") or key.endswith(".json"):
            print(f"Fetching s3://{bucket}/{key}")
            file_obj = s3_client.get_object(Bucket=bucket, Key=key)
            content = file_obj["Body"].read().decode("utf-8")

            if key.endswith(".json"):
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        # try to extract page_content or text, else use raw json
                        content = data.get("page_content", data.get("text", content))
                except json.JSONDecodeError:
                    pass

            documents.append(Document(page_content=content, metadata={"source": f"s3://{bucket}/{key}", "filename": key}))
            # Just fetch the first 3 for testing
            if len(documents) >= 3:
                break

    return documents

    return documents


def test_s3():
    print("--- TESTING COMPONENT 1: S3 FETCH ---")
    settings = get_eval_settings()
    docs = fetch_documents_from_s3(settings.s3_bucket, settings.s3_prefix)
    print(f"Returned {len(docs)} documents.")
    for d in docs:
        print(f"- {d.metadata['filename']} (Content preview: {d.page_content[:60].replace(chr(10), ' ')}...)")
    return docs


def test_llm():
    print("\n--- TESTING COMPONENT 2: GEMINI LLM ---")
    settings = get_eval_settings()
    from langchain_google_genai import ChatGoogleGenerativeAI

    try:
        # Using Gemini 3.1 Flash-Lite for text generation
        llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", google_api_key=settings.gemini_api_key)
        response = llm.invoke("Say 'Hello from Gemini!'")
        print(f"LLM Response: {response.content}")
        return True
    except Exception as e:
        print(f"LLM Error: {e}")
        return False


def test_ragas_generator(docs):
    print("\n--- TESTING COMPONENT 3: RAGAS TESTSET GENERATOR INIT ---")
    # Apply Ragas workaround first
    import sys
    import types

    if "langchain_community.chat_models.vertexai" not in sys.modules:
        dummy_module = types.ModuleType("langchain_community.chat_models.vertexai")
        dummy_module.ChatVertexAI = type("ChatVertexAI", (object,), {})
        sys.modules["langchain_community.chat_models.vertexai"] = dummy_module

    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    from ragas.testset import TestsetGenerator

    settings = get_eval_settings()

    try:
        # Gemini 3.1 Flash-Lite for Generation
        generator_llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", google_api_key=settings.gemini_api_key)
        # Gemini Embedding 2 for high quality vectors
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2", google_api_key=settings.gemini_api_key)

        generator = TestsetGenerator.from_langchain(llm=generator_llm, embedding_model=embeddings)
        print("Ragas TestsetGenerator initialized successfully!")
    except Exception as e:
        print(f"Generator Init Error: {e}")
        return None
    return generator


def test_ragas_generation(generator, docs):
    print("\n--- TESTING COMPONENT 4: RAGAS GENERATION ---")
    try:
        print("Starting generation using 1 document to create 1 test case...")
        # Use just 1 doc and generate 1 test case for a quick component test
        testset = generator.generate_with_langchain_docs(docs[2:3], testset_size=1)
        print("Generation successful!")
        df = testset.to_pandas()
        print("\nGenerated Testset Preview:")
        print(df.head())
        return df
    except Exception as e:
        print(f"Generation Error: {e}")
        return None


def test_s3_upload(df):
    print("\n--- TESTING COMPONENT 5: INCREMENTAL S3 UPLOAD ---")
    import io

    import boto3
    import pandas as pd
    from botocore.exceptions import ClientError

    settings = get_eval_settings()
    s3_client = boto3.client("s3", region_name=settings.aws_region)
    dataset_key = "evaluation/golden_dataset.csv"

    try:
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

        print(f"Appending {len(df)} new rows...")
        final_df = pd.concat([existing_df, df], ignore_index=True)

        print(f"Uploading combined dataset ({len(final_df)} total rows)...")
        csv_buffer = io.StringIO()
        final_df.to_csv(csv_buffer, index=False)

        s3_client.put_object(Bucket=settings.s3_bucket, Key=dataset_key, Body=csv_buffer.getvalue())
        print("Upload successful!")
        return True
    except Exception as e:
        print(f"S3 Upload Error: {e}")
        return False


if __name__ == "__main__":
    docs = test_s3()
    if docs:
        llm_ok = test_llm()
        if llm_ok:
            generator = test_ragas_generator(docs)
            if generator:
                df = test_ragas_generation(generator, docs)
                if df is not None and not df.empty:
                    test_s3_upload(df)
