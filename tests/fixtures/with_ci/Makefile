.PHONY: test lint build clean

test:
	pytest tests/

lint:
	ruff check src/

build:
	python -m build

clean:
	rm -rf dist/ build/

install:
	pip install -e .
