FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev --no-interaction

COPY libs/ libs/
COPY services/regime_hmm/ services/regime_hmm/

CMD ["python", "-m", "services.regime_hmm.src.main"]
