"""A resumed generation run must keep finished essays and give the rest the seeds it would have had.

Both `torch` and `transformers` are faked in `sys.modules`, so this runs on the lite tier too:
`generate_ai.main` only needs `manual_seed`, `no_grad`, and a 2-D id batch it can slice.
"""

import contextlib
import csv
import json
import sys
import types

from untell.bench import generate_ai


class _Ids:
    """A (1, n) id batch: just enough of a tensor for `.shape[1]` and `gen[0, start:]`."""

    def __init__(self, row):
        self.row = list(row)
        self.shape = (1, len(self.row))

    def __getitem__(self, key):
        if isinstance(key, tuple):
            batch, cols = key
            assert batch == 0
            return self.row[cols]
        assert key == 0
        return self.row


def _fake_torch(monkeypatch):
    state = {"seed": 0}

    def manual_seed(seed):
        state["seed"] = int(seed)

    mod = types.SimpleNamespace(
        manual_seed=manual_seed,
        initial_seed=lambda: state["seed"],
        no_grad=contextlib.nullcontext,
    )
    monkeypatch.setitem(sys.modules, "torch", mod)
    return mod


def _fake_transformers(monkeypatch, calls):
    torch = _fake_torch(monkeypatch)

    class Tok:
        @classmethod
        def from_pretrained(cls, _):
            return cls()

        def apply_chat_template(self, *a, **k):
            return {"input_ids": _Ids([0, 0, 0])}

        def decode(self, ids, skip_special_tokens=True):
            return f"essay seed={int(ids[0])}"

    class Model:
        @classmethod
        def from_pretrained(cls, _):
            return cls()

        def float(self):
            return self

        def eval(self):
            return self

        def generate(self, input_ids, **k):
            seed = torch.initial_seed()
            calls.append(seed)
            return _Ids(input_ids.row + [seed % 1000])

    mod = types.SimpleNamespace(AutoTokenizer=Tok, AutoModelForCausalLM=Model)
    monkeypatch.setitem(sys.modules, "transformers", mod)


def _csv(tmp_path):
    p = tmp_path / "p.csv"
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["prompt_name", "assignment"])
        w.writeheader()
        w.writerows([{"prompt_name": "A", "assignment": "Write A."},
                     {"prompt_name": "B", "assignment": "Write B."}])
    return str(p)


def test_resume_skips_finished_essays_and_keeps_seeds(tmp_path, monkeypatch):
    calls: list[int] = []
    _fake_transformers(monkeypatch, calls)
    src = _csv(tmp_path)
    full = tmp_path / "full.jsonl"
    generate_ai.main([src, "--per-prompt", "2", "--seed", "3", "--out", str(full)])
    want = [json.loads(line) for line in open(full)]
    assert len(want) == 4

    part = tmp_path / "part.jsonl"
    part.write_text("".join(json.dumps(r) + "\n" for r in want[:2]))
    calls.clear()
    generate_ai.main([src, "--per-prompt", "2", "--seed", "3", "--out", str(part), "--resume"])
    got = [json.loads(line) for line in open(part)]
    assert len(calls) == 2  # only the two missing essays were generated
    assert got == want


def test_without_resume_the_file_is_rewritten(tmp_path, monkeypatch):
    _fake_transformers(monkeypatch, [])
    src = _csv(tmp_path)
    out = tmp_path / "o.jsonl"
    out.write_text('{"id": "stale"}\n')
    generate_ai.main([src, "--per-prompt", "1", "--out", str(out)])
    assert [json.loads(line)["id"] for line in open(out)] == ["modern:A:0", "modern:B:0"]
