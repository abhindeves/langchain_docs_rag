#!/bin/bash
# -----------------------------------------------------------------------------
# AWS Lambda ZIP Packaging Script
# This script exports dependencies using uv, installs them targeting a Linux platform,
# copies indexer-service source code and shared-lib code, and zips the bundle.
# -----------------------------------------------------------------------------
set -e

# Target variables
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKSPACE_DIR="$DIR/../.."
BUILD_DIR="$DIR/build"
ZIP_FILE="$DIR/lambda_function.zip"

echo "=== Cleaning previous build environment ==="
rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

echo "=== Exporting workspace requirements using uv ==="
# Export dependencies, omitting local shared-lib package since we copy its source code directly.
# Target manylinux_2_28 (compatible with Amazon Linux 2023 / Python 3.12 Lambda runtime).
uv pip compile "$DIR/pyproject.toml" \
  --no-emit-package shared-lib \
  --python-platform x86_64-manylinux_2_28 \
  --python-version 3.12 \
  -o "$BUILD_DIR/requirements.txt"

echo "=== Installing dependencies for Linux architecture ==="
# Use uv pip install with target directory, python-platform, python-version tags, and --no-build
uv pip install -r "$BUILD_DIR/requirements.txt" \
  --target "$BUILD_DIR" \
  --python-platform x86_64-manylinux_2_28 \
  --python-version 3.12 \
  --no-build

echo "=== Copying source directories to build target ==="
# Copy indexer-service source package
cp -r "$DIR/src/indexer" "$BUILD_DIR/"

# Copy shared-lib source package
cp -r "$WORKSPACE_DIR/shared-lib/src/rag_shared" "$BUILD_DIR/"

echo "=== Pre-downloading FastEmbed model ==="
PYTHONPATH="$BUILD_DIR" HF_HUB_DISABLE_SYMLINKS=1 uv run python -c "
import os
os.environ['FASTEMBED_CACHE_PATH'] = '$BUILD_DIR/fastembed_cache'
from fastembed import SparseTextEmbedding
# Instantiating downloads model files locally
model = SparseTextEmbedding(model_name='Qdrant/bm25')
"

echo "=== Cleaning up build assets ==="
# Remove temp requirements
rm -f "$BUILD_DIR/requirements.txt"
# Remove pytest caches, debug files, build configs, and compiled pyc/pyo files to optimize package size
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$BUILD_DIR" -type f -name "*.pyc" -delete
find "$BUILD_DIR" -type f -name "*.pyo" -delete

echo "=== Generating ZIP file ==="
# Zip the contents of BUILD_DIR into ZIP_FILE
cd "$BUILD_DIR"
zip -r "$ZIP_FILE" . > /dev/null
cd "$DIR"

# Cleanup build directory
rm -rf "$BUILD_DIR"

echo "=== Lambda ZIP bundle successfully built! ==="
