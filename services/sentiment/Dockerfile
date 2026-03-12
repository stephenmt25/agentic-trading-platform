FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev --no-interaction

COPY libs/ libs/
COPY services/sentiment/ services/sentiment/

CMD ["python", "-m", "services.sentiment.src.main"]
