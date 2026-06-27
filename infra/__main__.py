import json

import pulumi
import pulumi_aws as aws

# 1. DynamoDB Table for Ingestion Tracking
sync_table = aws.dynamodb.Table(
    "document-sync-status",
    name="DocumentSyncStatus",
    billing_mode="PAY_PER_REQUEST",
    hash_key="doc_id",
    attributes=[
        aws.dynamodb.TableAttributeArgs(
            name="doc_id",
            type="S",
        )
    ],
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)

# 2. S3 Bucket for Ingested Documents
ingestion_bucket = aws.s3.Bucket(
    "rag-document-store",
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)


# 3. SQS Ingestion Queue with Dead-Letter Queue (DLQ)
dlq = aws.sqs.Queue(
    "rag-ingestion-dlq",
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)

ingestion_queue = aws.sqs.Queue(
    "rag-ingestion-queue",
    redrive_policy=dlq.arn.apply(
        lambda arn: json.dumps(
            {
                "deadLetterTargetArn": arn,
                "maxReceiveCount": 3,
            }
        )
    ),
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)

# SQS Queue Policy to allow S3 events
queue_policy = aws.sqs.QueuePolicy(
    "rag-ingestion-queue-policy",
    queue_url=ingestion_queue.id,
    policy=pulumi.Output.all(ingestion_queue.arn, ingestion_bucket.arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowS3ToPublishEvents",
                        "Effect": "Allow",
                        "Principal": {"Service": "s3.amazonaws.com"},
                        "Action": "sqs:SendMessage",
                        "Resource": args[0],
                        "Condition": {"ArnEquals": {"aws:SourceArn": args[1]}},
                    }
                ],
            }
        )
    ),
)

# Native S3 Bucket Notification configuration
bucket_notification = aws.s3.BucketNotification(
    "rag-s3-notification",
    bucket=ingestion_bucket.id,
    queues=[
        aws.s3.BucketNotificationQueueArgs(
            queue_arn=ingestion_queue.arn,
            events=["s3:ObjectCreated:*"],
            filter_prefix="raw/pages/",
            filter_suffix=".json",
        )
    ],
    opts=pulumi.ResourceOptions(depends_on=[queue_policy]),
)


# Outputs
pulumi.export("ingestion_bucket_name", ingestion_bucket._name)
pulumi.export("dynamodb_table_name", sync_table.name)
# Export Queue URL
pulumi.export("ingestion_queue_url", ingestion_queue.id)
