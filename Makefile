.PHONY: help install hooks lint format test check scrub privacy ci frame sample render forms load db clean

PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

help:
	@echo "Setup"
	@echo "  make install     create .venv and install the package with dev extras"
	@echo ""
	@echo "Quality"
	@echo "  make lint        black --check, isort --check, flake8"
	@echo "  make format      apply black and isort"
	@echo "  make test        pytest"
	@echo "  make check       validate data/tables/*.csv against the schema"
	@echo "  make privacy     fail if git is tracking anything personal"
	@echo "  make scrub       re-derive the public tables from the private ones"
	@echo "  make hooks       install the pre-push guard"
	@echo "  make ci          everything CI runs"
	@echo ""
	@echo "Pipeline"
	@echo "  make frame       build data/frame.csv from the raw sources"
	@echo "  make sample      draw the batch in config/batch.yaml"
	@echo "  make render      write bilingual letters and the RA worklist"
	@echo "  make forms       print the Google Form specification"
	@echo "  make load        merge everything in data/intake_raw/"
	@echo "  make db          rebuild schema.sql and rti.db from the tables"

install: hooks
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev,scrapers]"

hooks:
	@cp hooks/pre-push .git/hooks/pre-push
	@chmod +x .git/hooks/pre-push
	@echo "pre-push hook installed: pushes are blocked if personal data is tracked"

lint:
	$(BIN)/black --check src tests
	$(BIN)/isort --check-only src tests
	$(BIN)/flake8 src tests

format:
	$(BIN)/black src tests
	$(BIN)/isort src tests

test:
	$(BIN)/pytest

check:
	$(BIN)/rti-check

scrub:
	$(BIN)/rti-scrub

privacy:
	$(BIN)/rti-scrub --check

ci: lint test check privacy

frame:
	$(BIN)/rti-build-frame

sample:
	$(BIN)/rti-sample

render:
	$(BIN)/rti-render

forms:
	$(BIN)/rti-forms

load:
	$(BIN)/rti-load --all

db:
	$(BIN)/rti-build-db

clean:
	rm -rf build dist *.egg-info .pytest_cache rti.db
	find . -name '__pycache__' -not -path './.git/*' -exec rm -rf {} +
