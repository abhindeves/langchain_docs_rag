import hashlib
import json
import os
import re
import sys
from urllib.parse import urlparse

# Ensure local directories are in path for configuration imports
sys.path.append(os.path.join(os.path.dirname(__file__), "shared-lib/src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "services/indexer-service/src"))

import boto3

from rag_shared.config import get_shared_settings


def get_sanitized_name(url: str) -> str:
    """
    Converts a URL to a safe, human-readable S3 directory / filename prefix.
    """
    parsed = urlparse(url)
    combined = f"{parsed.netloc}{parsed.path}"
    # Replace anything that isn't a letter, number, hyphen, or underscore with a single underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", combined)
    # Remove duplicate underscores and strip trailing/leading ones
    return re.sub(r"_+", "_", sanitized).strip("_")


settings = get_shared_settings()

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
table = dynamodb.Table("DocumentSyncStatus")
bucket_name = settings.s3_bucket

target_url = "https://docs.langchain.com/llms-full.txt"
target_url_hash = hashlib.md5(target_url.encode("utf-8")).hexdigest()
target_url_name = get_sanitized_name(target_url)

old_manifest_key = f"manifests/{target_url_hash}.json"
manifest_key = f"manifests/{target_url_name}.json"

print("=== Starting S3 Migration & Bootstrap script ===")
print(f"Target URL: {target_url}")
print(f"Target Hash (Old): {target_url_hash}")
print(f"Target Name (New): {target_url_name}")
print(f"S3 Bucket: {bucket_name}")
print(f"AWS Region: {settings.aws_region}")

# 1. Scan DynamoDB
print("\nScanning DynamoDB Sync status...")
try:
    response = table.scan()
    items = response.get("Items", [])
except Exception as e:
    print(f"ERROR: Failed to scan DynamoDB Table: {e}")
    sys.exit(1)

manifest = {}
print(f"Found {len(items)} items in DynamoDB. Migrating S3 files...")

success_count = 0
for item in items:
    doc_id = item["doc_id"]
    content_hash = item["content_hash"]
    hashed_filename = hashlib.md5(doc_id.encode("utf-8")).hexdigest()

    # Candidate Paths
    old_hash_s3_key = f"raw/pages/{target_url_hash}/{hashed_filename}.json"
    old_root_s3_key = f"raw/pages/{hashed_filename}.json"
    new_s3_key = f"raw/pages/{target_url_name}/{hashed_filename}.json"

    source_key = None

    # A. Check if the object is already at the new key (already migrated)
    try:
        s3.head_object(Bucket=bucket_name, Key=new_s3_key)
        source_key = new_s3_key
    except s3.exceptions.ClientError:
        pass

    # B. If not at new key, try to copy from old hash folder
    if not source_key:
        try:
            s3.copy_object(Bucket=bucket_name, CopySource={"Bucket": bucket_name, "Key": old_hash_s3_key}, Key=new_s3_key)
            s3.delete_object(Bucket=bucket_name, Key=old_hash_s3_key)
            source_key = new_s3_key
            success_count += 1
        except s3.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code != "NoSuchKey":
                print(f"Error copying from hash folder for {doc_id}: {e}")

    # C. If still not copied, try to copy from root folder
    if not source_key:
        try:
            s3.copy_object(Bucket=bucket_name, CopySource={"Bucket": bucket_name, "Key": old_root_s3_key}, Key=new_s3_key)
            s3.delete_object(Bucket=bucket_name, Key=old_root_s3_key)
            source_key = new_s3_key
            success_count += 1
        except s3.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                print(f"Skipping (File missing in both S3 sources): {hashed_filename}.json")
            else:
                print(f"Error copying from root folder for {doc_id}: {e}")

    if source_key:
        manifest[doc_id] = {"hash": content_hash, "s3_key": new_s3_key}

# 3. Upload manifest to S3
if manifest:
    print(f"\nUploading manifest containing {len(manifest)} items to s3://{bucket_name}/{manifest_key}...")
    try:
        s3.put_object(Bucket=bucket_name, Key=manifest_key, Body=json.dumps(manifest, indent=2), ContentType="application/json")
        print(f"\n=== Bootstrap successful! {success_count} files migrated. Manifest saved. ===")

        # 4. Clean up old manifest in S3 if it exists
        try:
            s3.delete_object(Bucket=bucket_name, Key=old_manifest_key)
            print(f"Deleted old hash manifest: {old_manifest_key}")
        except Exception:
            pass
    except Exception as e:
        print(f"ERROR: Failed to upload manifest: {e}")
else:
    print("No items to migrate or manifest is empty.")
