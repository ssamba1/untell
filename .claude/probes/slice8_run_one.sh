#!/bin/bash
# Run ONE chunk under coverage (append mode); pytest summary goes to a per-chunk log.
# usage: bash slice8_run_one.sh <CHUNK_VAR_NAME> [extra test files...]
set +m
cd "C:/Users/Admin/goals/scratch-8" || exit 9
export PYTHONPATH="C:/Users/Admin/goals/scratch-8"
export PATH="/c/Users/Admin/Humanize/.venv/Scripts:$PATH"
source /c/Users/Admin/Humanize/.claude/probes/slice8_chunks.sh
PY=/c/Users/Admin/Humanize/.venv/Scripts/python.exe
SRC="--source=untell.scripts.voice,untell.scripts.latex,untell.scripts.entailment,untell.scripts.roles,untell.scripts.tells,untell.scripts.verify,untell.scripts.audit,untell.scripts.explain,untell.scripts.io_utils,untell._env,untell._retry,untell.languages,untell.config,untell.humanness"
VAR="$1"; shift
FILES="${!VAR} $*"
CFG="${COVERAGE_FILE:-.coverage}"
LOG=/c/Users/Admin/Humanize/.claude/probes/slice8_chunk_${VAR}.log
echo "CHUNK=$VAR CFG=$CFG" > "$LOG"
COVERAGE_FILE="$CFG" $PY -m coverage run --append $SRC -m pytest -q $FILES -p no:cacheprovider >> "$LOG" 2>&1
echo "CHUNK_DONE=$VAR" >> "$LOG"
tail -4 "$LOG"
