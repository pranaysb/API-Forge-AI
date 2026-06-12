FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.8.3

RUN pip install "poetry==$POETRY_VERSION"

COPY pyproject.toml /app/
# Copy poetry.lock if it exists, otherwise just pyproject.toml
COPY poetry.loc[k] /app/

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY . /app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
