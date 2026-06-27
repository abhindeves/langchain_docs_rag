import os
import sys

import boto3

# Dynamically add indexer-service/src and shared-lib/src relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

sys.path.append(os.path.join(workspace_root, "services", "indexer-service", "src"))
sys.path.append(os.path.join(workspace_root, "shared-lib", "src"))

from indexer.lambda_handler import worker_handler  # noqa: E402

from rag_shared.config import get_shared_settings  # noqa: E402


def run_local_worker():
    settings = get_shared_settings()
    sqs_client = boto3.client("sqs", region_name=settings.aws_region)

    print("=== Starting Local Worker Integration Test ===")
    print(f"SQS Queue URL: {settings.sqs_queue_url}")
    print(f"Qdrant Host: {settings.qdrant_host}:{settings.qdrant_port}")

    processed_count = 0

    while True:
        # 1. Receive messages from SQS
        print("Polling SQS for messages...")
        response = sqs_client.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=5,  # Long polling
        )

        messages = response.get("Messages", [])
        if not messages:
            print("No more messages in the queue. Exiting.")
            break

        print(f"Received {len(messages)} messages from queue.")

        # 2. Package into a Lambda-like event structure
        event = {
            "Records": [
                {
                    "body": msg["Body"],
                    "receiptHandle": msg["ReceiptHandle"],
                    "messageId": msg["MessageId"],
                }
                for msg in messages
            ]
        }

        try:
            # 3. Call the actual lambda handler logic
            print("Invoking worker_handler...")
            result = worker_handler(event, None)
            print(f"worker_handler execution result: {result}")

            # 4. If successful, delete the processed messages from SQS
            for msg in messages:
                sqs_client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
                print(f"Deleted message {msg['MessageId']} from SQS.")

            processed_count += len(messages)

        except Exception as e:
            print(f"Error during execution: {e}")
            print("Leaving messages in the SQS queue for retry.")
            break

    print(f"\n=== Local Worker Run Finished. Processed {processed_count} messages. ===")


if __name__ == "__main__":
    run_local_worker()
