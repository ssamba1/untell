"""Single source of truth for the numeric bounds shared by the CLI and the REST surfaces.

Every bound the CLI validates (``--threshold``, ``--max-iters``, ``--best-of``, ``--confirm``,
``--seed``, ``--top``) is enforced at the REST edge too, and the two copies drifted apart once
(``test_surface_parity`` pins the sharing so it cannot silently happen again). The values live
here, as plain tuples, so that BOTH consumers can import them without paying for the other's
stack:

- ``untell/api_server.py`` builds its ``Annotated[float, Field(ge=..., le=...)]`` request-model
  aliases from these tuples (so FastAPI keeps validating with the same numbers).
- ``untell/scripts/run.py`` reads the tuples directly for its argparse ``type=`` validators.

Before this module existed the CLI imported ``untell.api_server`` to read the bounds off the
pydantic metadata, and ``untell.api_server`` imports FastAPI at module level — so every
``untell humanize`` invocation paid a ~0.5s FastAPI/starlette/anyio/pydantic import just to
validate ``--threshold``. MEASURED (median of 5, cold subprocess): ``import untell.scripts.run``
0.757s before, 0.23s after, on a machine where ``import pydantic`` alone is 0.223s.

Types are deliberate: ``_Seed``'s high bound is ``2**64 - 1``, an int no float can hold exactly,
so the tuples keep the API-declared types rather than casting to float (see ``run._bounds``).
"""

# `threshold` is a probability.
_Probability = (0.0, 1.0)
# Counts multiply the work a single request does; the upper limits stop a runaway rather than
# second-guess a caller. 0 is a MEANING for `_Confirm` ("do not re-confirm") and `_Top`
# ("flag none"), so their low bounds are 0, not 1.
_Iters = (1, 100)
_BestOf = (1, 32)
_Confirm = (0, 32)
# A seed names a stream, so two different seeds must be two different streams. CPython's
# `random.seed()` takes the ABSOLUTE value of an int, which makes -1 and 1 the same one: measured
# byte-identical output for both, where 0, 2, 7 and 12345 each differed. The upper bound is the
# range of the text-derived default (blake2b, 8 bytes), so a request can name any stream the
# service would pick on its own.
_Seed = (0, 2**64 - 1)
# `--top` decides WHICH sentences come back flagged — the entire output of that operation. The
# high bound is above any reachable sentence count, since MAX_INPUT_CHARS caps a document near
# 650 sentences; a bare int made `order[:top]` a negative slice (measured: -1 flagged 2 of 3
# sentences, more than `--top 1`).
_Top = (0, 10_000)
