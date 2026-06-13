# API Forge AI

API Forge AI is an autonomous, agentic system built with LangGraph that ingests an OpenAPI schema and dynamically generates, tests, and self-heals Python SDK clients.

## Overview

The system orchestrates multiple LLM-powered agents to ensure that the generated SDK is structurally sound, semantically correct, and fully tested against real or mocked network conditions.

Features include:
- **Automatic SDK Generation**: Takes any valid OpenAPI schema and generates a robust Python `ApiClient` and Pydantic V2 models.
- **Self-Healing Graph**: A LangGraph workflow that includes Schema Validation, SDK Validation, and an intelligent Diagnoser that patches the SDK in memory until all tests pass.
- **Automated Mocking**: Automatically builds `httpx.MockTransport` test stubs to validate endpoints without live network dependency.
- **Installable Packages**: Final SDK output is bundled with `pyproject.toml` and ready for `pip install .`.

## Getting Started

### Prerequisites
- Python 3.12+
- Poetry
- Node.js (for the frontend)
- PostgreSQL (or an equivalent database supported by SQLAlchemy)

### Local Setup

1. **Backend**:
    ```bash
    cd backend
    poetry install
    cp .env.example .env # Set your GROQ_API_KEY
    poetry run alembic upgrade head
    poetry run uvicorn app.main:app --reload --port 8000
    ```

2. **Frontend**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

### Environment Variables
You must set your LLM API keys in the `.env` file for the backend. The primary logic is configured for Groq:
```
GROQ_API_KEY=your_key_here
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deep dive into the LangGraph state machine and the responsibilities of the Planner, Coder, Executor, and Diagnoser nodes.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to run tests, write new features, and understand the workflow.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
