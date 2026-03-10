FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up Poetry
ENV POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_VERSION=1.7.0
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

# Install dependencies first for caching layers
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-dev

# Copy the rest of the application
COPY . .

# Install the application package
RUN poetry install --no-dev

CMD ["python", "src/main.py"]
