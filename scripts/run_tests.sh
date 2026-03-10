#!/bin/bash
set -e

cleanup() {
  echo "Tearing down test environment..."
  docker compose -f deploy/docker-compose.test.yml down -v
}
trap cleanup EXIT

echo "Starting test infrastructure..."
docker compose -f deploy/docker-compose.test.yml up -d

echo "Waiting for test Redis and TimescaleDB to become healthy..."
until docker compose -f deploy/docker-compose.test.yml ps redis | grep -q "(healthy)"; do sleep 1; done
until docker compose -f deploy/docker-compose.test.yml ps timescaledb | grep -q "(healthy)"; do sleep 1; done

echo "Running tests..."
# Tests are run using poetry which will handle migrations for unit/integration logic
export AION_REDIS_URL="redis://localhost:6379/1"
export AION_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/aion_test"
export AION_TRADING_ENABLED=false

poetry run pytest tests/ -v --cov=libs --cov=services --cov-report=term-missing
