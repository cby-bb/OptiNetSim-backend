# Optical Network Topology Management API

This project provides a RESTful API service for managing optical network topologies, built with FastAPI and MongoDB.

## Features

-   Full CRUD operations for Networks, Topology Elements, Connections, and Services.
-   Endpoints to manage global network settings (Simulation, Spectrum Info, Span).
-   Network import and export functionalities.
-   Asynchronous from the ground up.
-   Data validation using Pydantic.

## Project Structure

The project follows a modular structure to separate concerns:

```
optical-network-api/
├── .env                  # Environment variables
├── pyproject.toml        # Project dependencies (for uv)
├── README.md             # This file
└── optical_network_manager/
    ├── api/                # API routers and endpoints
    ├── core/               # Core configuration and DB connection
    ├── crud/               # Database interaction logic
    ├── main.py             # FastAPI application entrypoint
    └── models/             # Pydantic data models
```

## Setup and Installation

### Prerequisites

-   Python 3.9+
-   `uv` (Python package installer)
-   A running MongoDB instance

### Steps

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd optical-network-api
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```

3.  **Install dependencies using `uv`:**
    ```bash
    uv pip install -r pyproject.toml
    # Or more simply with uv >= 0.1.18
    uv sync
    ```

4.  **Configure Environment Variables:**
    Create a `.env` file in the project root by copying the example:
    ```bash
    cp .env.example .env
    ```
    Modify the `.env` file with your MongoDB connection details:
    ```env
    MONGO_URI="mongodb://localhost:27017"
    MONGO_DB_NAME="optical_network_topology"
    ```

## Running the Application

To start the development server, run the following command from the project root directory:

```bash
uvicorn optical_network_manager.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

You can access the interactive API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.

## Database Design

The application uses a single MongoDB collection named `networks`. Each document in this collection represents an entire optical network, embedding its elements, connections, services, and global configurations. This design choice simplifies data retrieval for a complete network and ensures data consistency.

-   `network_id` corresponds to the MongoDB `_id`.
-   `element_id`, `connection_id`, and `service_id` are UUIDs generated at the application level.
