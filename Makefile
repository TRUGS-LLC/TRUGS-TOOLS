# TRUGS-TOOLS — contributor entry points.
#   make dev    installs the language CLI editable with its test dependencies (.[test]).
#   make check  runs pytest tests/, then trug validate folder.trug.json.
.PHONY: dev check

dev:
	pip install -e ".[test]"

check:
	pytest tests/
	trug validate folder.trug.json
