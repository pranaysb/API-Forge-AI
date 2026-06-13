# Contributing to API Forge AI

We welcome contributions! Please follow the guidelines below to ensure a smooth development process.

## Branching Strategy
- **main**: The stable branch. All deployments happen from here.
- **feature/XYZ**: Create a feature branch off `main` for any new development.
- **fix/XYZ**: Create a fix branch off `main` for any bug fixes.

## Local Development Workflow
1. Fork the repository and clone it locally.
2. Install dependencies using Poetry for the backend (`cd backend && poetry install`) and npm for the frontend (`cd frontend && npm install`).
3. Make your changes and run existing tests. If you create new scripts to test behavior, please place them in `backend/scripts/` (these are ignored by git to keep history clean).
4. Do not commit temporary `.pyc` caches, `.log` files, or generated zip artifacts. Our `.gitignore` should catch most of these, but please be mindful.

## Pull Requests
- Ensure your commits are logically structured (e.g. separate your schema updates from your UI updates).
- Reference any open issues in your PR description.
- Provide a summary of the problem and how you fixed it. If your change affects the Agent graph, please describe the impact on node routing.

## Submitting Issues
If you encounter a bug or have a feature request, please open a detailed GitHub issue. Include the OpenAPI schema that caused the failure, if applicable.
