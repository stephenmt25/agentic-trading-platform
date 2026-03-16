# ---------------------
# Stage 1: Builder
# ---------------------
FROM python:3.11-slim AS builder

# Install system dependencies needed for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up Poetry
ENV POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VERSION=1.7.0
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

# Install dependencies first for caching layers
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-dev

# Copy the rest of the application
COPY . .

# Install the application package
RUN poetry install --no-dev

# ---------------------
# Stage 2: Runtime
# ---------------------
FROM python:3.11-slim AS runtime

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtualenv and application from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

# Ensure the virtualenv Python is on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["python", "src/main.py"]
