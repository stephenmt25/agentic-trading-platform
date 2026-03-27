#!/bin/bash
set -e

# Start local infrastructure
docker compose -f deploy/docker-compose.yml up --build -d

echo "Waiting for Redis to be healthy..."
until docker compose -f deploy/docker-compose.yml ps redis | grep -q "(healthy)"; do
  sleep 2
done

echo "Waiting for TimescaleDB to be healthy..."
until docker compose -f deploy/docker-compose.yml ps timescaledb | grep -q "(healthy)"; do
  sleep 2
done

echo "Applying migrations..."
for f in migrations/versions/*.sql; do
    echo "Running $f"
    docker exec -i $(docker compose -f deploy/docker-compose.yml ps -q timescaledb) psql -U postgres -d praxis_trading < "$f"
done

echo "Infrastructure is up and running."
# TODO: Execute python scripts/seed_data.py if necessary

# Follow logs of all services
docker compose -f deploy/docker-compose.yml logs -f
