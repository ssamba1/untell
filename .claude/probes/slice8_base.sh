#!/bin/bash
# Slice 8 baseline coverage — sequential chunks, coverage --append, in the CLEAN worktree.
set +m
cd "C:/Users/Admin/goals/scratch-8" || exit 9
export PYTHONPATH="C:/Users/Admin/goals/scratch-8"
export PATH="/c/Users/Admin/Humanize/.venv/Scripts:$PATH"
source /c/Users/Admin/Humanize/.claude/probes/slice8_chunks.sh
PY=/c/Users/Admin/Humanize/.venv/Scripts/python.exe
SRC="--source=untell.scripts.voice,untell.scripts.latex,untell.scripts.entailment,untell.scripts.roles,untell.scripts.tells,untell.scripts.verify,untell.scripts.audit,untell.scripts.explain,untell.scripts.io_utils,untell._env,untell._retry,untell.languages,untell.config,untell.humanness"
LOG=/c/Users/Admin/Humanize/.claude/probes/slice8_base
rm -f .coverage
$PY -m coverage run $SRC -m pytest -q $A1_VOICE_LATEX -p no:cacheprovider > $LOG.a1.log 2>&1; echo "A1 EXIT=$?" >> $LOG.a1.log
$PY -m coverage run --append $SRC -m pytest -q $A2_ENTAIL_ROLES -p no:cacheprovider > $LOG.a2.log 2>&1; echo "A2 EXIT=$?" >> $LOG.a2.log
$PY -m coverage run --append $SRC -m pytest -q $A3_EXPLAIN_IO -p no:cacheprovider > $LOG.a3.log 2>&1; echo "A3 EXIT=$?" >> $LOG.a3.log
$PY -m coverage run --append $SRC -m pytest -q $A4_ENV_RETRY_LANG_CONFIG -p no:cacheprovider > $LOG.a4.log 2>&1; echo "A4 EXIT=$?" >> $LOG.a4.log
$PY -m coverage run --append $SRC -m pytest -q $B1_VERIFY -p no:cacheprovider > $LOG.b1.log 2>&1; echo "B1 EXIT=$?" >> $LOG.b1.log
$PY -m coverage run --append $SRC -m pytest -q $B2_AUDIT -p no:cacheprovider > $LOG.b2.log 2>&1; echo "B2 EXIT=$?" >> $LOG.b2.log
$PY -m coverage run --append $SRC -m pytest -q $B3_TELLS -p no:cacheprovider > $LOG.b3.log 2>&1; echo "B3 EXIT=$?" >> $LOG.b3.log
$PY -m coverage run --append $SRC -m pytest -q $B4_HUMANNESS -p no:cacheprovider > $LOG.b4.log 2>&1; echo "B4 EXIT=$?" >> $LOG.b4.log
$PY -m coverage run --append $SRC -m pytest -q tests/test_console_scripts_respond.py -p no:cacheprovider > $LOG.b5.log 2>&1; echo "B5 EXIT=$?" >> $LOG.b5.log
$PY -m coverage report > $LOG.report.txt 2>&1
$PY -m coverage report --show-missing > $LOG.missing.txt 2>&1
echo "ALL DONE"
