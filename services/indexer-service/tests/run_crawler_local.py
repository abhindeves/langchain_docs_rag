import os
import sys

# Dynamically add indexer-service/src and shared-lib/src relative to script
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))

sys.path.append(os.path.join(workspace_root, "services", "indexer-service", "src"))
sys.path.append(os.path.join(workspace_root, "shared-lib", "src"))

from indexer.manifest_crawler import run_manifest_crawler  # noqa: E402

from rag_shared.config import get_shared_settings  # noqa: E402

if __name__ == "__main__":
    settings = get_shared_settings()
    print(f"\nResolved Settings: Bucket={settings.s3_bucket}")

    target_url = "https://docs.langchain.com/llms-full.txt"
    print(f"=== Executing Manifest Crawler for URL: {target_url} ===")
    result = run_manifest_crawler(target_url)
    print(f"Manifest Crawler run finished. Processed {result} files.")
