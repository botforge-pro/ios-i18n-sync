.PHONY: install test clean

install:
	pip install -e .
	pip install -r requirements-dev.txt

test:
	pytest

test-cov:
	pytest --cov=i18n_sync --cov-report=term-missing

clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete