.PHONY: lint test-unit test-integration test-all run-local build install

install:
	poetry install

lint:
	poetry run black libs services tests
	poetry run isort libs services tests
	poetry run ruff check libs services tests
	poetry run mypy libs services

test-unit:
	poetry run pytest tests/unit -v --cov=libs --cov=services --cov-report=term-missing

test-integration:
	poetry run pytest tests/integration -v

test-all: test-unit test-integration

run-local:
	docker compose -f deploy/docker-compose.yml up --build -d

build:
	docker compose -f deploy/docker-compose.yml build
