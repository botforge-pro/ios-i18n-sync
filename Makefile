.PHONY: install format lint test-build test build test-cov clean

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

clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
