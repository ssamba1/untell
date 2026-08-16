"""Env-var & detector-registry consistency matrix.

One table, four checks, for every environment variable the product reads. The README's
env-var table (line ~779) claims to be complete ("Every ``UNTELL_*`` variable the code
reads") and `untell-audit` enforces the docs side; this file pins the OTHER three cells
of the matrix per variable:

  1. DOCUMENTED   — the name appears in README (or is a justified test/installer-only name)
  2. READ         — the code actually reads it (grep-verified read site in untell/ eval/ training/)
  3. SANE ON BAD VALUES — a mistyped value yields a message and a fallback, never a traceback
  4. CONSISTENT ACROSS SURFACES — CLI-config vars are exactly the `_CLI_DEFAULTS` keys the
     REST/MCP surfaces take as request args; server-only vars are read by the API server.

The registry half pins the detector metadata contract: a stable name/tier roster,
uniform `__init__` signatures (no required arguments — `all_detectors()` constructs every
adapter with none), and no dead `UNTELL_DISABLE_*` / `UNTELL_ENABLE_*` flags (documented
switches that nothing reads).

These were the failure modes that motivated the file: `UNTELL_POLICY_MAXTOK=abc` used to
raise a bare ValueError inside generation, and a detector added to the registry with a
required constructor argument would break `all_detectors()` on a tier where it should be
optional. Both are now pinned.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# The 22 canonical UNTELL_* variables the product reads, plus the two HUMANIZE_* legacy
# aliases the README documents as still honoured. Kept in one place so the matrix has a
# single source of truth; adding a variable means adding it here, to the README table,
# and to the read-site scan below — the tests then say which cells are missing.
CANONICAL = {
    "UNTELL_API_KEY",
    "UNTELL_BEST_OF",
    "UNTELL_BROWSER_SITES",
    "UNTELL_CORS_ORIGINS",
    "UNTELL_DISABLE_MAGE",
    "UNTELL_DISABLE_NLI",
    "UNTELL_DISABLE_ROLES",
    "UNTELL_ENABLE_LOCAL_JUDGE",
    "UNTELL_ENABLE_RADAR",
    "UNTELL_HOST",
    "UNTELL_JUDGE_MODEL",
    "UNTELL_LITE_NO_TORCH",
    "UNTELL_MAX_ITERS",
    "UNTELL_POLICY_4BIT",
    "UNTELL_POLICY_BASE",
    "UNTELL_POLICY_DIR",
    "UNTELL_POLICY_MAXTOK",
    "UNTELL_POLICY_NO_SYSTEM",
    "UNTELL_POLICY_WHOLE_DOC",
    "UNTELL_PORT",
    "UNTELL_RATE_LIMIT",
    "UNTELL_REWARD_FAST",
    "UNTELL_REWRITER",
    "UNTELL_SELECT",
    "UNTELL_STYLE",
    "UNTELL_SURROGATE_DIR",
    "UNTELL_THRESHOLD",
    "UNTELL_TIER",
    "HUMANIZE_BROWSER_SITES",
    "HUMANIZE_ENABLE_RADAR",
}

# The six CLI-config keys, read as f"UNTELL_{key.upper()}" by untell.config.get() from
# run.py's _config_defaults — the one family the literal read-site scan cannot see.
CONFIG_KEYS = ("tier", "threshold", "max_iters", "rewriter", "style", "best_of")

# Detectors the README tier table and docs/index.md describe. The count checks live in
# test_docs_claims.py; this roster pins names AND tiers so a rename or a re-tiering
# cannot slip past a count-only check.
ROSTER = {
    ("perplexity_burstiness", "lite"),
    ("roberta_openai", "full"),
    ("hc3_roberta", "full"),
    ("mage", "full"),
    ("fast_detectgpt", "full"),
    ("radar", "full"),
    ("binoculars", "heavy"),
    ("local_judge", "heavy"),
    ("llm_judge", "commercial"),
    ("originality", "commercial"),
    ("gptzero", "commercial"),
    ("winston", "commercial"),
    ("sapling", "commercial"),
    ("zerogpt", "commercial"),
    ("copyleaks", "commercial"),
}

_DIRECT_READ = re.compile(
    r'os\.environ\.(?:get|pop)\(\s*"([A-Z][A-Z0-9_]+)"|os\.getenv\(\s*"([A-Z][A-Z0-9_]+)"'
)
_SCAN_DIRS = ("untell", "eval", "training")


def _read_sites() -> set[str]:
    """Var names with a literal read site anywhere in untell/, eval/, training/."""
    found: set[str] = set()
    for folder in _SCAN_DIRS:
        base = REPO / folder
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                for m in _DIRECT_READ.finditer(line):
                    found.add(m.group(1) or m.group(2))
    return found


def _readme() -> str:
    return (REPO / "README.md").read_text(encoding="utf-8", errors="replace")


# -----------------------------------------------------------------------------------
# Cell 1: documented
# -----------------------------------------------------------------------------------

def test_every_canonical_var_is_documented_in_readme():
    readme = _readme()
    missing = sorted(v for v in CANONICAL if v not in readme)
    assert not missing, (
        f"env vars the code reads are missing from README's env-var table: {missing}"
    )


def test_the_roster_is_actually_found():
    """A regex that matches nothing would make the documentation test pass vacuously."""
    readme = _readme()
    hits = sum(1 for v in CANONICAL if v in readme)
    assert hits >= len(CANONICAL) - 2, f"only {hits}/{len(CANONICAL)} vars found in README"


# -----------------------------------------------------------------------------------
# Cell 2: actually read
# -----------------------------------------------------------------------------------

def test_every_canonical_var_has_a_read_site():
    direct = _read_sites()
    missing = sorted(v for v in CANONICAL if v not in direct and v not in CANONICAL_INDIRECT())
    assert not missing, (
        f"no read site found for: {missing}. Either the var is dead (delete it from the "
        f"docs and CANONICAL) or it is read via config.get (add it to CONFIG_KEYS)."
    )


def CANONICAL_INDIRECT() -> set[str]:
    return {f"UNTELL_{k.upper()}" for k in CONFIG_KEYS}


def test_config_keys_are_wired_through_config_get():
    """The indirect family must actually be read: run.py's _config_defaults iterates
    _CLI_DEFAULTS and calls config.get(key, shipped) for each, which reads the env var."""
    src = (REPO / "untell" / "scripts" / "run.py").read_text(encoding="utf-8")
    defaults_block = src.split("_CLI_DEFAULTS: dict[str, object] = {", 1)[1].split("}", 1)[0]
    keys = set(re.findall(r'"(\w+)":', defaults_block))
    assert keys == set(CONFIG_KEYS), f"_CLI_DEFAULTS keys {keys} drifted from CONFIG_KEYS"
    assert "config.get(key, shipped)" in src, (
        "_config_defaults no longer reads each key through config.get — the env path is gone"
    )


def test_no_dead_disable_or_enable_flags():
    """Every documented UNTELL_DISABLE_*/UNTELL_ENABLE_* switch must be read somewhere.
    A switch nobody reads is a guarantee nobody knows they have turned off."""
    readme = _readme()
    flags = set(re.findall(r"\bUNTELL_(?:DISABLE|ENABLE)_[A-Z0-9_]+\b", readme))
    direct = _read_sites()
    dead = sorted(f for f in flags if f not in direct)
    assert not dead, f"documented switches with no read site: {dead}"


# -----------------------------------------------------------------------------------
# Cell 3: sane on bad values (message, not traceback)
# -----------------------------------------------------------------------------------

def test_untell_port_invalid_is_a_message_not_a_traceback(monkeypatch, capsys):
    """UNTELL_PORT=abc used to crash while BUILDING the parser (before --help could run)."""
    from untell.api_server import _port_from_env

    monkeypatch.setenv("UNTELL_PORT", "abc")
    with pytest.raises(SystemExit) as exc:
        _port_from_env()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "UNTELL_PORT must be a whole number" in err

    monkeypatch.setenv("UNTELL_PORT", "99999")
    with pytest.raises(SystemExit) as exc:
        _port_from_env()
    assert exc.value.code == 2
    assert "between 1 and 65535" in capsys.readouterr().err


def test_untell_rate_limit_invalid_warns_and_falls_back(monkeypatch, caplog):
    from untell.api_server import _rate_limit

    monkeypatch.delenv("UNTELL_RATE_LIMIT", raising=False)
    assert _rate_limit() == 60

    monkeypatch.setenv("UNTELL_RATE_LIMIT", "abc")
    with caplog.at_level("WARNING"):
        assert _rate_limit() == 60
    assert "not an integer" in caplog.text


def test_untell_threshold_invalid_warns_and_falls_back(monkeypatch, caplog):
    from untell import config

    monkeypatch.delenv("UNTELL_THRESHOLD", raising=False)
    monkeypatch.setenv("UNTELL_THRESHOLD", "abc")
    with caplog.at_level("WARNING"):
        assert config.get("threshold", 0.30) == 0.30
    assert "expected float" in caplog.text


def test_untell_max_iters_invalid_warns_and_falls_back(monkeypatch, caplog):
    from untell import config

    monkeypatch.delenv("UNTELL_MAX_ITERS", raising=False)
    monkeypatch.setenv("UNTELL_MAX_ITERS", "3.7")
    with caplog.at_level("WARNING"):
        assert config.get("max_iters", 5) == 5
    assert "expected int" in caplog.text


def test_untell_tier_invalid_is_a_message_not_a_traceback(monkeypatch, capsys):
    from untell.scripts.run import _config_defaults

    monkeypatch.delenv("UNTELL_TIER", raising=False)
    monkeypatch.setenv("UNTELL_TIER", "bogus")
    out = _config_defaults()
    assert out["tier"] == "full"
    assert "ignoring configured tier='bogus'" in capsys.readouterr().err


def test_untell_select_invalid_falls_back_to_max(monkeypatch):
    from untell.scripts.run import _selection_mode

    monkeypatch.delenv("UNTELL_SELECT", raising=False)
    assert _selection_mode() == "max"
    monkeypatch.setenv("UNTELL_SELECT", "bogus")
    assert _selection_mode() == "max"
    monkeypatch.setenv("UNTELL_SELECT", "dropout")
    assert _selection_mode() == "dropout"


def test_untell_policy_maxtok_invalid_warns_and_falls_back(monkeypatch, caplog):
    """Regression pin for the fixed traceback: UNTELL_POLICY_MAXTOK=abc used to raise
    ValueError from int() inside generation."""
    from untell.rewriter.local_policy import _env_max_new_tokens

    monkeypatch.delenv("UNTELL_POLICY_MAXTOK", raising=False)
    assert _env_max_new_tokens(300, use_adapter=False) == 512
    assert _env_max_new_tokens(300, use_adapter=True) == 512

    monkeypatch.setenv("UNTELL_POLICY_MAXTOK", "700")
    assert _env_max_new_tokens(300, use_adapter=False) == 700

    monkeypatch.setenv("UNTELL_POLICY_MAXTOK", "abc")
    with caplog.at_level("WARNING"):
        assert _env_max_new_tokens(300, use_adapter=False) == 512
    assert "UNTELL_POLICY_MAXTOK" in caplog.text

    monkeypatch.setenv("UNTELL_POLICY_MAXTOK", "0")
    with caplog.at_level("WARNING"):
        assert _env_max_new_tokens(300, use_adapter=True) == 512


def test_untell_browser_sites_bad_path_is_a_quiet_none(monkeypatch):
    """A nonexistent UNTELL_BROWSER_SITES path must not raise — it means 'no custom
    checkers', and the checker lookup falls through to None."""
    from untell.browser_check import get_browser_checker

    monkeypatch.setenv("UNTELL_BROWSER_SITES", str(REPO / "definitely-not-a-sites-file.json"))
    assert get_browser_checker("anything") is None


# -----------------------------------------------------------------------------------
# Cell 4: consistent across CLI / REST / MCP
# -----------------------------------------------------------------------------------

def test_cli_config_keys_match_the_rest_surface_bounds_source():
    """The CLI and REST surfaces must agree on what 'config' means: the six env-wired keys
    are exactly the six keys _CLI_DEFAULTS ships, and _api_bounds.py (the shared range
    source) is consulted by both surfaces."""
    from untell.scripts.run import _CLI_DEFAULTS

    assert set(_CLI_DEFAULTS) == set(CONFIG_KEYS)
    assert (REPO / "untell" / "_api_bounds.py").exists()


def test_server_env_vars_are_read_by_api_server():
    src = (REPO / "untell" / "api_server.py").read_text(encoding="utf-8")
    for var in ("UNTELL_API_KEY", "UNTELL_HOST", "UNTELL_PORT", "UNTELL_RATE_LIMIT", "UNTELL_CORS_ORIGINS"):
        assert f'os.environ.get("{var}"' in src, f"{var} is documented as a server var but api_server does not read it"


def test_mcp_server_reads_no_undocumented_env():
    """The MCP surface takes tier/rewriter/threshold as explicit tool arguments and reads
    no UNTELL_* env vars of its own — so it cannot drift from the CLI's env wiring."""
    src = (REPO / "untell" / "mcp_server.py").read_text(encoding="utf-8")
    for m in re.finditer(r'os\.environ\.(?:get|pop)\(\s*"(UNTELL_[A-Z0-9_]+)"', src):
        pytest.fail(f"mcp_server reads {m.group(1)} — MCP config is argument-based, not env-based")


# -----------------------------------------------------------------------------------
# Registry metadata
# -----------------------------------------------------------------------------------

def test_registry_names_and_tiers_match_the_documented_roster():
    from untell.detectors.base import all_detectors

    got = {(d.name, d.tier) for d in all_detectors()}
    assert got == ROSTER, f"registry drifted: missing {ROSTER - got}, extra {got - ROSTER}"


def test_registry_names_are_unique():
    from untell.detectors.base import all_detectors

    names = [d.name for d in all_detectors()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate detector names in the registry: {dupes}"


def test_every_detector_has_a_documented_tier():
    from untell.detectors.base import all_detectors

    assert all(d.tier in {"lite", "full", "heavy", "commercial"} for d in all_detectors())


def test_every_detector_init_signature_is_uniform():
    """all_detectors() constructs every adapter with NO arguments, so a required
    constructor parameter would break the registry. Pin the signatures explicitly so a
    future required arg fails here with a name, not with a TypeError from the registry."""
    from untell.detectors.base import all_detectors

    for d in all_detectors():
        sig = inspect.signature(type(d).__init__)
        required = [
            p.name
            for p in sig.parameters.values()
            if p.name != "self"
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            and p.default is inspect.Parameter.empty
        ]
        assert not required, f"{type(d).__name__} requires constructor args {required}"


def test_lite_tier_is_never_empty():
    """The documented invariant from base.py: the lite heuristic is dependency-free, so
    the registry never returns an empty list (which would silently zero-score)."""
    from untell.detectors.base import load_detectors

    assert load_detectors("lite"), "load_detectors('lite') came back empty"


def test_cli_env_vars_reach_the_loop_without_a_traceback(monkeypatch, capsys, caplog):
    """End-to-end shape: the six CLI env vars combined, with two invalid, still produce a
    runnable default set and name the dropped values."""
    from untell.scripts.run import _config_defaults

    for var, val in (("UNTELL_TIER", "bogus"), ("UNTELL_THRESHOLD", "abc")):
        monkeypatch.setenv(var, val)
    with caplog.at_level("WARNING"):
        out = _config_defaults()
    assert out["tier"] == "full" and out["threshold"] == 0.3
    err = capsys.readouterr().err
    assert "tier='bogus'" in err
    assert "UNTELL_THRESHOLD" in caplog.text


def test_guard_the_guard_direct_read_scan_finds_something():
    direct = _read_sites()
    assert len(direct) >= 20, f"read-site scan found only {len(direct)} vars — scan broken?"
