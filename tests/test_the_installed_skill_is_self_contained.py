"""SKILL.md named a file the installer does not ship.

Both installers copy `<repo>/untell` to the skills directory and nothing else — no `docs/`, no
`eval/`, no root files. The audit already checks that every script SKILL.md invokes exists, but it
resolves against the REPO, where all of those are present. A reference to anything outside
`untell/` therefore passes every check and is broken for every user who installed the documented
way.

FOUND by simulating the copy: 24 path-shaped references in SKILL.md, 16 resolve inside the
installed tree, 7 are example filenames that resolve nowhere by design (`their-writing.txt`,
`candidate.txt`, `path.json`), and one was real:

    docs/free-ceiling-measured.md

Now a URL, which works from an installed skill and from the repo alike.

This checks the property the audit cannot: not "does this path exist" but "does it survive the
install". The two differ by exactly the set of files the installer leaves behind.
"""

from __future__ import annotations

import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SKILL_DIR = _ROOT / "untell"
_SKILL_MD = _SKILL_DIR / "SKILL.md"

# Filenames used as EXAMPLES in prose rather than as references to shipped files. Named explicitly
# so a genuinely missing file cannot hide among them.
_EXAMPLE_FILENAMES = frozenset({
    "their-writing.txt", "candidate.txt", "path.json", "tmp/untell_scoring.txt",
    "score.py", "quality.py", "ai-tells.md",
})

_PATHLIKE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|md|json|yaml|yml|toml|txt|html|cff)\b")


def _installed_files() -> set[str]:
    """What the installer actually copies: the `untell/` subtree, rooted at the skill directory."""
    return {
        p.relative_to(_SKILL_DIR).as_posix()
        for p in _SKILL_DIR.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def _references() -> list[str]:
    text = _SKILL_MD.read_text(encoding="utf-8")
    # Drop URLs first: a path inside one is part of the URL, not a repo reference.
    text = re.sub(r"https?://\S+", " ", text)
    return sorted({ref.lstrip("./") for ref in _PATHLIKE.findall(text)})


def test_the_installers_still_copy_only_the_untell_directory() -> None:
    """The premise. If an installer ever shipped more, this file's whole argument changes."""
    sh = (_ROOT / "install.sh").read_text(encoding="utf-8")
    ps1 = (_ROOT / "install.ps1").read_text(encoding="utf-8")
    assert 'cp -r "$TMP/untell/untell" "$DEST"' in sh, "install.sh no longer copies untell/ alone"
    assert 'Copy-Item -Recurse (Join-Path $tmp "untell") $dest' in ps1, (
        "install.ps1 no longer copies untell/ alone"
    )


def test_every_repo_path_named_in_skill_md_survives_installation() -> None:
    installed = _installed_files()
    broken = []
    for ref in _references():
        if ref in _EXAMPLE_FILENAMES:
            continue
        candidate = ref[len("untell/"):] if ref.startswith("untell/") else ref
        if candidate in installed:
            continue
        if any(name.endswith("/" + candidate) for name in installed):
            continue  # named bare, e.g. `references/ai-tells.md` written as `ai-tells.md`
        if (_ROOT / ref).exists():
            broken.append(ref)

    assert not broken, (
        f"SKILL.md names {broken}, which exist in the repo but are NOT shipped by the installer — "
        f"broken for everyone who installed the documented way. Use a URL instead of a repo path."
    )


def test_the_check_sees_a_real_number_of_references() -> None:
    """Guards the guard. A regex that stopped matching, or an exclusion list that swallowed
    everything, would make the test above pass while inspecting nothing."""
    refs = _references()
    assert len(refs) >= 12, f"only {len(refs)} path-shaped references found in SKILL.md"
    assert len(_installed_files()) >= 30, "the installed-tree listing looks empty"


def test_a_path_outside_untell_would_be_caught() -> None:
    """Known positive. `docs/` is the directory the real defect pointed into."""
    installed = _installed_files()
    outside = "docs/free-ceiling-measured.md"
    assert (_ROOT / outside).exists(), "fixture path no longer exists in the repo"
    assert outside not in installed
    assert not any(name.endswith("/" + outside) for name in installed)


@pytest.mark.parametrize("name", sorted(_EXAMPLE_FILENAMES))
def test_each_excluded_name_is_genuinely_an_example(name: str) -> None:
    """An exclusion list is a place to hide a real defect. Every entry must be either a file the
    repo does not have at that path (so it is prose), or one the installer does ship."""
    installed = _installed_files()
    shipped = name in installed or any(n.endswith("/" + name) for n in installed)
    assert shipped or not (_ROOT / name).exists(), (
        f"{name} exists in the repo but is not shipped, and is excluded as an example — that is "
        f"exactly the defect this file exists to catch"
    )
