.PHONY: install format lint test-build test build test-cov

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -e . --no-deps

format:
	ruff format .

lint:
	ruff check .
	ruff format --check .

test-build:
	python -m compileall -q i18n_sync tests

test: test-build
	pytest

build: lint test

test-cov:
	pytest --cov=i18n_sync --cov-report=term-missing
