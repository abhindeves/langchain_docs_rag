import os
import sys

# Dynamically add indexer-service/src and shared-lib/src relative to script
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))

sys.path.append(os.path.join(workspace_root, "services", "indexer-service", "src"))
sys.path.append(os.path.join(workspace_root, "shared-lib", "src"))

from indexer.crawler import run_crawler  # noqa: E402

from rag_shared.config import get_shared_settings  # noqa: E402

if __name__ == "__main__":
    settings = get_shared_settings()
    print(f"\nResolved Settings: Bucket={settings.s3_bucket}")

    print("=== Executing Crawler ===")
    result = run_crawler()
    print(f"Crawler run finished. Dispatched {result} files to S3.")
