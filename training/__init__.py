"""RL/alignment training scaffold — the GPU moat (StealthRL/MASH/AuthorMist style).

The reward (``training.reward``) is pure-python over our own detector ensemble, so it is testable
without a GPU. The trainer (``training.rl_humanizer``) requires a GPU + ``[train]`` extra and is NOT
run in CI — it is the one-command-away moat described in docs/best-humanizer-roadmap.md.
"""
