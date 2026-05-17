PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: venv install test lint gui clean

venv:
	python3 -m venv .venv
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -r requirements.txt

test:
	$(PY) -m pytest

gui:
	PYTHONPATH=src $(PY) main.py

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
