# TRUGS-TOOLS — contributor entry points.
#   make dev    provisions the documented dev/test environment (editable installs of
#               the language CLI and the bundled trugs-folder cartography package).
#   make check  is the Tier-1 gate: the bundled trugs-folder suite (the 554-test green
#               floor) plus Layer-4 self-validation of this repo's own folder.trug.json
#               against the TRUGS CORE rules the engine implements.
.PHONY: dev check

dev:
	pip install -e ".[test]"
	pip install -e ./trugs-folder

check:
	pytest trugs-folder/tests/
	trug validate folder.trug.json
