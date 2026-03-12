FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev --no-interaction

COPY libs/ libs/
COPY services/ta_agent/ services/ta_agent/

CMD ["python", "-m", "services.ta_agent.src.main"]
