# Use a python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy the workspace configuration and package specifications
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY shared-lib shared-lib
COPY services/api-service services/api-service
COPY services/indexer-service services/indexer-service
COPY services/evaluation-service services/evaluation-service

# Sync workspace dependencies specifically for the api-service
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package api-service --frozen --no-dev

# Final runtime stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source files (matching your root shared-lib folder location)
COPY shared-lib /app/shared-lib
COPY services/api-service /app/services/api-service

# Set path to use virtual environment binary folder
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Run the FastAPI app via Uvicorn
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
