# Makefile

VENV := .venv
PYTHON := $(VENV)/Scripts/python.exe

.PHONY: install run test ingest clean

# Create venv if it doesn't exist
$(VENV)/Scripts/activate:
	@echo "Creating virtual environment..."
	@if not exist $(VENV) (python -m venv $(VENV))

# Install dependencies
install: $(VENV)/Scripts/activate
	@echo "Upgrading pip and installing requirements..."
	"$(PYTHON)" -m pip install --upgrade pip
	"$(PYTHON)" -m pip install -r requirements.txt

# Run tests with coverage
test: $(VENV)/Scripts/activate
	@echo "Running tests with coverage..."
	"$(PYTHON)" -m pytest tests/ --maxfail=1 --disable-warnings -q --cov=. --cov-report=term-missing --cov-fail-under=80

# Remove virtual environment
clean:
	@echo "Deactivating and removing virtual environment..."
	@if exist .venv (rmdir /s /q .venv)
