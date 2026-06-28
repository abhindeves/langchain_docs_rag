import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import pulumi
import pulumi_aws as aws

from rag_shared.config import get_shared_settings

settings = get_shared_settings()

# Retrieve stack configurations for artifacts bucket & key
config = pulumi.Config()
aws_config = pulumi.Config("aws")

artifacts_bucket_name = config.get("artifacts_bucket") or "rag-document-store-57d6fd4"
lambda_s3_key = config.get("lambda_s3_key") or "lambda_function.zip"
aws_region = aws_config.require("region")


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
    visibility_timeout_seconds=900,
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


# =============================================================================
# 4. AWS Lambda Compute & Scheduler Layer (CI Decoupled)
# =============================================================================


# --- Worker Lambda IAM Role & Policies ---
worker_role = aws.iam.Role(
    "worker-lambda-role", assume_role_policy=json.dumps({"Version": "2012-10-17", "Statement": [{"Action": "sts:AssumeRole", "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}}]})
)

aws.iam.RolePolicyAttachment("worker-lambda-basic", role=worker_role.name, policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")

aws.iam.RolePolicyAttachment("worker-lambda-sqs", role=worker_role.name, policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole")

aws.iam.RolePolicy(
    "worker-lambda-permissions",
    role=worker_role.name,
    policy=pulumi.Output.all(sync_table.arn, ingestion_bucket.arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"], "Resource": args[0]},
                    {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": f"{args[1]}/*"},
                    {"Effect": "Allow", "Action": ["bedrock:InvokeModel"], "Resource": "*"},
                ],
            }
        )
    ),
)

# --- Worker Lambda Function ---
worker_lambda = aws.lambda_.Function(
    "worker-lambda",
    runtime="python3.12",
    role=worker_role.arn,
    handler="indexer.lambda_handler.worker_handler",
    s3_bucket=artifacts_bucket_name,
    s3_key=lambda_s3_key,
    timeout=900,
    memory_size=512,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "s3_bucket": ingestion_bucket.id,
            "aws_region": aws_region,
            "qdrant_host": settings.qdrant_host,
            "qdrant_api_key": settings.qdrant_api_key or "",
        }
    ),
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)

# SQS to Lambda Mapping (Concurrency Throttle)
aws.lambda_.EventSourceMapping(
    "worker-sqs-mapping",
    event_source_arn=ingestion_queue.arn,
    function_name=worker_lambda.name,
    batch_size=1,
    scaling_config={"maximum_concurrency": 2},
)

# --- Crawler Lambda IAM Role & Policies ---
crawler_role = aws.iam.Role(
    "crawler-lambda-role", assume_role_policy=json.dumps({"Version": "2012-10-17", "Statement": [{"Action": "sts:AssumeRole", "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}}]})
)

aws.iam.RolePolicyAttachment("crawler-lambda-basic", role=crawler_role.name, policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")

aws.iam.RolePolicy(
    "crawler-lambda-permissions",
    role=crawler_role.name,
    policy=pulumi.Output.all(sync_table.arn, ingestion_bucket.arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem"],
                        "Resource": args[0],
                    },
                    {"Effect": "Allow", "Action": ["s3:PutObject"], "Resource": f"{args[1]}/*"},
                ],
            }
        )
    ),
)

# --- Crawler Lambda Function ---
crawler_lambda = aws.lambda_.Function(
    "crawler-lambda",
    runtime="python3.12",
    role=crawler_role.arn,
    handler="indexer.lambda_handler.crawl_handler",
    s3_bucket=artifacts_bucket_name,
    s3_key=lambda_s3_key,
    timeout=300,
    memory_size=256,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "s3_bucket": ingestion_bucket.id,
            "aws_region": aws_region,
        }
    ),
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)

# --- EventBridge Scheduler Trigger ---
cron_rule = aws.cloudwatch.EventRule(
    "crawler-cron-rule",
    schedule_expression="cron(0 0 * * ? *)",  # Daily UTC 00:00 trigger
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)

cron_target = aws.cloudwatch.EventTarget("crawler-cron-target", rule=cron_rule.name, arn=crawler_lambda.arn)

aws.lambda_.Permission("crawler-cron-permission", action="lambda:InvokeFunction", function=crawler_lambda.name, principal="events.amazonaws.com", source_arn=cron_rule.arn)


# =============================================================================
# Outputs
# =============================================================================
pulumi.export("ingestion_bucket_name", ingestion_bucket.id)
pulumi.export("dynamodb_table_name", sync_table.name)
pulumi.export("ingestion_queue_url", ingestion_queue.id)
pulumi.export("worker_lambda_arn", worker_lambda.arn)
pulumi.export("crawler_lambda_arn", crawler_lambda.arn)
