#!/bin/bash
# Run ONE chunk under coverage in the MAIN tree (shipped code). 
# usage: bash slice8_run_main.sh <CHUNK_VAR_NAME> [extra test files...]
set +m
cd /c/Users/Admin/Humanize || exit 9
export PYTHONPATH=
export PATH="/c/Users/Admin/Humanize/.venv/Scripts:$PATH"
source /c/Users/Admin/Humanize/.claude/probes/slice8_chunks.sh
PY=/c/Users/Admin/Humanize/.venv/Scripts/python.exe
SRC="--source=untell.scripts.voice,untell.scripts.latex,untell.scripts.entailment,untell.scripts.roles,untell.scripts.tells,untell.scripts.verify,untell.scripts.audit,untell.scripts.explain,untell.scripts.io_utils,untell._env,untell._retry,untell.languages,untell.config,untell.humanness"
VAR="$1"; shift
FILES="${!VAR} $*"
CFG="${COVERAGE_FILE:-.coverage.main}"
LOG=/c/Users/Admin/Humanize/.claude/probes/slice8_main_${VAR}.log
echo "CHUNK=$VAR CFG=$CFG" > "$LOG"
COVERAGE_FILE="$CFG" $PY -m coverage run --append $SRC -m pytest -q $FILES -p no:cacheprovider >> "$LOG" 2>&1
echo "CHUNK_DONE=$VAR" >> "$LOG"
tail -2 "$LOG"
