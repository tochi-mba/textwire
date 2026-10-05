.DEFAULT_GOAL := help
UV ?= uv
# Tools run as modules through the interpreter, never through the virtualenv's .exe shims:
# a Windows Application Control policy on the reference development machine blocks those
# shims (pytest.exe, mypy.exe, lint-imports.exe). This spelling works everywhere.
PY := $(UV) run python

.PHONY: help install fmt lint type imports test cov check run docker clean test-live \
	vectors vectors-check simulate doctor bench bench-record setup

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install everything
	$(UV) sync --group dev

fmt: ## Format the code and apply safe lint fixes
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

lint: ## Lint and format check (no fixes)
	$(UV) run ruff format --check .
	$(UV) run ruff check .

type: ## Strict type check
	$(PY) -m mypy

imports: ## Enforce the architecture contracts
	$(PY) scripts/lint_imports.py

test: ## Tests with 100% branch coverage enforced
	$(PY) -P -m pytest --cov --cov-report=term-missing

cov: ## Write an HTML coverage report to htmlcov/
	$(PY) -P -m pytest --cov --cov-report=html

check: lint type imports test ## Everything CI runs for the server, on one interpreter

test-live: ## Tests that send real SMS through Twilio (needs server/.env; costs money)
	$(PY) -P -m pytest -m live --no-cov

run: ## Run the server: poll Twilio, answer requests
	$(PY) -m textwire serve

simulate: ## Browse from the terminal with a virtual phone and recorded pages
	$(PY) -m textwire simulate --offline

doctor: ## Check this machine and the configuration
	$(PY) -m textwire doctor

vectors: ## Regenerate the golden vectors in ../protocol/vectors
	$(PY) -m textwire vectors regen

vectors-check: ## Fail if the committed golden vectors drifted from the reference
	$(PY) -m textwire vectors check

setup: ## Guided setup: the Twilio account, number and keys, written to .env
	$(PY) -m textwire setup

bench: ## SMS per page and pipeline speed against ../benchmarks/baseline.json
	$(PY) -m textwire bench

bench-record: ## Record this checkout's numbers as the new baseline
	$(PY) -m textwire bench --record

docker: ## Build the container image
	docker build -t textwire:local .

clean: ## Remove caches and build output
	rm -rf .pytest_cache .mypy_cache .ruff_cache .hypothesis .import_linter_cache htmlcov \
		.coverage coverage.xml junit.xml build dist
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
