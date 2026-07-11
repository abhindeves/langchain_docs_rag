# API Service

The API Service provides the main interface for querying the RAG platform. It is a FastAPI-based application that exposes endpoints for health checks, embedding, and (in the future) retrieval and chat.

## API Endpoints

The following endpoints are currently available:

### Health Checks

*   `GET /health/liveness`
    *   A simple liveness probe to confirm that the API service is running.
    *   **Returns:** `{"status": "ok"}`

*   `GET /health/readiness`
    *   A readiness probe that checks the service's ability to connect to the Qdrant vector database.
    *   **Returns:** `{"status": "ready", "database": "connected"}` if successful.
    *   **Returns:** A `503 Service Unavailable` error if the database is not reachable.

### Embedding

*   `POST /embed`
    *   Generates an embedding for a given text string using the configured Bedrock model.
    *   **Request Body:**
        ```json
        {
          "text": "The text to be embedded."
        }
        ```
    *   **Returns:**
        ```json
        {
          "embedding": [0.1, 0.2, ...]
        }
        ```

## Core Components

*   **`main.py`:** The main entry point for the FastAPI application. It initializes the application, sets up middleware, exception handlers, and defines the health check and embedding endpoints.
    *   **Source:** [`services/api-service/src/api/main.py`](../../services/api-service/src/api/main.py)
*   **`router.py`:** Includes the API routers for different versions of the API.
    *   **Source:** [`services/api-service/src/api/router.py`](../../services/api-service/src/api/router.py)
*   **`config.py`:** Manages the API's configuration settings.
    *   **Source:** [`services/api-service/src/api/config.py`](../../services/api-service/src/api/config.py)
*   **`v1/`:** This directory is intended to house the version 1 API endpoints for features like chat and retrieval, which are currently under development.

## Future Development

As indicated by the project roadmap and the file structure, the following features are planned for the API service:

*   **Retrieval Endpoint:** An endpoint for performing hybrid (dense and sparse) semantic search over the document corpus.
*   **Chat Endpoint:** An endpoint for engaging in a chat-based interaction with the RAG model.
