"""A resumed generation run must keep finished essays and give the rest the seeds it would have had."""

import csv
import json
import sys
import types

from untell.bench import generate_ai


class _Enc(dict):
    def __init__(self):
        import torch

        super().__init__(input_ids=torch.zeros((1, 3), dtype=torch.long))


def _fake_transformers(monkeypatch, calls):
    import torch

    class Tok:
        @classmethod
        def from_pretrained(cls, _):
            return cls()

        def apply_chat_template(self, *a, **k):
            return _Enc()

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
            return torch.cat([input_ids, torch.tensor([[seed % 1000]])], dim=1)

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
