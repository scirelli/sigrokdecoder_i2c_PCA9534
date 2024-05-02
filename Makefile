SHELL:=/usr/bin/env bash

VENV_DIR=.venv
VENV_BIN=$(VENV_DIR)/bin

PIP=$(VENV_BIN)/pip
PYTHON_EXE=python3.12
PYTHON=$(VENV_BIN)/python3
PYENV_INSTALL=0
PYTHON_INSTALL=0
PYTHON_VERSION=$(shell cat .python-version 2> /dev/null || echo '3.12.2')
IS_CORRECT_PYTHON_VERSION=$(shell $(PYTHON_EXE) --version | grep -oE '$(PYTHON_VERSION)')

PRU_SRC=pru/src
PRU_FILE=hambone.pru0

define MSG_INSTALL_PYTHON3

Python3 must be at version $(PYTHON_VERSION) or greater.
Install by running 'install_python_pyenv.sh' located in the 'scripts' directory.

./scripts/install_python_pyenv.sh

endef


ifeq "$(IS_CORRECT_PYTHON_VERSION)" ""
$(warning "$(MSG_INSTALL_PYTHON3)")
endif


.PHONY: all
all: test

$(VENV_DIR):
	@echo 'Creating a virtual environment'
	@$(PYTHON_EXE) -m venv --prompt $(notdir $(CURDIR)) ./$(VENV_DIR)
	@echo 'Environment created. Run "source ./$(VENV_DIR)/bin/activate" or "make shell" to activate the virtual environment.\n"deactivate" or "exit" to exit it.'

.update-pip: ## Update pip
	@$(PIP) install -U 'pip'

.install-deps-dev: $(VENV_DIR)
	@$(PIP) install --require-virtualenv --requirement requirements-dev.txt
	@touch .install-deps-dev

.develop: .install-deps-dev
	@$(PIP) install --require-virtualenv --editable .
	@touch .develop

.PHONY: install-dev
install-dev: .develop ## Install development environment, in a virtual environment.

.PHONY: install-prod
install-prod:  ## Install non-dev environment
	@python3 -m pip install --target . --requirement requirements.txt

.PHONY: test
test: .develop  ## Run unit tests
	@$(VENV_BIN)/pytest -q

.PHONY: vtest
vtest: .develop ## Verbose tests
	@$(VENV_BIN)/pytest -v

.PHONY: vvtest
vvtest: .develop ## More verbose tests
	@$(VENV_BIN)/pytest -vv

.PHONY: dbtest
dbtest: .develop ## Debuggable tests
	@$(VENV_BIN)/pytest --capture=no -vv

.PHONY: viewCoverage
viewCoverage: htmlcov ## View the last coverage run
	open -a "Google Chrome" htmlcov/index.html

.PHONY: shell
shell: $(VENV_DIR) ## Open a virtual environment
	@echo 'Activating virtual environment.' && $(SHELL) --init-file <(echo ". ~/.bashrc; . $(VENV_BIN)/activate;")

.PHONY: clean
clean: ## Remove all generated files and folders
	@$(VENV_BIN)/pre-commit uninstall || true
	@rm -rf .venv
	@rm -rf `find . -name __pycache__`
	@rm -f `find . -type f -name '*.py[co]' `
	@rm -f .coverage
	@rm -rf htmlcov
	@rm -rf build
	@rm -rf cover
	@rm -f .develop
	@rm -f .flake
	@rm -rf *.egg-info
	@rm -f .install-deps-dev
	@rm -f .install-deps
	@rm -rf .mypy_cache
	@python setup.py clean || true
	@pkill -SIGTERM socat
	@rm -rf .eggs
	@rm -rf src/*.egg-info
	@rm -rf .pytest_cache/

.PHONY: list
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

.PHONY : help
help :
	@grep -E '^[[:alnum:]_-]+[[:blank:]]?:.*##' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# @if ! command -v pre-commit &> /dev/null; then echo You need to add "'""${HOME}/.local/bin""'" to your path. Or if you are using Pyenv run "'"pyenv rehash"'" ; false ; fi
