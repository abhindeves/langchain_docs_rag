import os
import sys

import boto3

# Dynamically add indexer-service/src and shared-lib/src relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

sys.path.append(os.path.join(workspace_root, "services", "indexer-service", "src"))
sys.path.append(os.path.join(workspace_root, "shared-lib", "src"))

from indexer.crawler import run_crawler  # noqa: E402

from shared.config import get_shared_settings  # noqa: E402


def bootstrap_aws_resources():
    print("=== Bootstrapping AWS Resources ===")
    sts_client = boto3.client("sts")
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs")

    # 1. Get AWS Account ID to ensure S3 bucket uniqueness
    account_id = sts_client.get_caller_identity()["Account"]
    region = get_shared_settings().aws_region

    bucket_name = f"rag-document-store-{account_id}"
    queue_name = f"rag-ingestion-queue-{account_id}"

    # 2. Create S3 Bucket in target region if it does not exist
    print(f"Checking S3 Bucket: {bucket_name} in region {region}...")
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print("S3 Bucket already exists.")
    except Exception:
        print("S3 Bucket does not exist. Creating...")
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"Created S3 Bucket: {bucket_name}")

    # 3. Create SQS Queue and get the full URL
    print(f"Checking SQS Queue: {queue_name}...")
    try:
        response = sqs_client.create_queue(QueueName=queue_name)
        queue_url = response["QueueUrl"]
        print(f"SQS Queue is ready: {queue_url}")
    except Exception as e:
        print(f"Failed to create SQS queue: {e}")
        sys.exit(1)

    # 4. Update the local .env file in the workspace root
    env_path = os.path.join(workspace_root, ".env")
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            env_lines = f.readlines()

    # Filter out any existing entries to avoid duplication
    env_lines = [
        line
        for line in env_lines
        if not line.startswith("s3_bucket") and not line.startswith("sqs_queue_url")
    ]

    # Append the new settings
    env_lines.append(f'\ns3_bucket="{bucket_name}"\n')
    env_lines.append(f'sqs_queue_url="{queue_url}"\n')

    with open(env_path, "w") as f:
        f.writelines(env_lines)
    print("Updated local .env file with S3 Bucket and SQS Queue URL configurations.")


if __name__ == "__main__":
    bootstrap_aws_resources()

    # Reload settings after modifying .env
    from shared.config import get_shared_settings

    settings = get_shared_settings()
    print(
        f"\nResolved Settings: Bucket={settings.s3_bucket}, "
        f"SQS={settings.sqs_queue_url}\n"
    )

    print("=== Executing Crawler ===")
    result = run_crawler()
    print(f"Crawler run finished. Pushed {result} jobs to SQS.")
