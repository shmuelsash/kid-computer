# One task-runner interface, same verbs as the rest of the fleet.
# Everything runs through uv so the environment stays isolated.

.PHONY: dev check test build fmt lint types clean

dev:
	uv run python -m kidcomputer

check: fmt lint types
	@echo "All checks passed."

fmt:
	uv run ruff format --check .

lint:
	uv run ruff check .

types:
	uv run mypy

test:
	uv run pytest

build:
	uv run pyinstaller --noconfirm --onefile --windowed --name KidComputer app_entry.py

clean:
	rm -rf build dist *.spec __pycache__ .pytest_cache .mypy_cache .ruff_cache
