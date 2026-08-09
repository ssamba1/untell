# Security Policy

## Reporting a vulnerability

If you find a security issue — a secret-handling bug, an injection in the browser/MCP paths, an
unsafe-deserialization, a supply-chain concern, or anything that could harm a user running this tool —
please report it **privately**:

- Use GitHub's **[Report a vulnerability](https://github.com/ssamba1/untell/security/advisories/new)**
  (Security → Advisories), **or**
- Open a minimal issue that says *"security — please contact me"* **without** the exploit details, and we'll
  move it to a private channel.

Please **do not** open a public issue with a working exploit before it's fixed.

We aim to acknowledge reports within a few days and to fix confirmed issues promptly. Thank you for
disclosing responsibly.

## Scope & handling of secrets

- **API keys are never committed.** Commercial-detector and LLM keys are read from environment variables or a
  gitignored `.env` (see [.env.example](.env.example)). The CLIs auto-load `.env`; real shell vars win.
- **Key-gated by design.** No commercial-detector or hosted-LLM call runs unless you set its key — nothing
  bills silently.
- **No telemetry.** This tool does not phone home. The only network calls are the detector/LLM APIs *you*
  configure and the optional `--browser` checker you point at a site.

## Dependency advisories

Every CI run executes `pip-audit` against the installed dependency set and prints what it finds.
The step is **advisory — it does not fail the build**, and that is a deliberate choice rather than
an oversight: a CVE landing in a transitive package turns the build red on a schedule nobody here
controls, and a red build that everyone learns to ignore is worse than an amber one that gets read.

Reproduce it locally:

```bash
pip install pip-audit && pip-audit --desc
```

Known, as of 2026-08-09, from a real run: `mcp` 1.28.0 (fixed in 1.28.1) and `torch` 2.12.1 (fixed
in 2.13.0) are both admitted by our floors, which are `mcp>=1.0` and `torch>=2.0`. Those floors have
**not** been raised, because pip-audit reports a fix version and not an affected *range* — writing
`mcp>=1.28.1` would drop every user on an older-but-unaffected release to fix a version we have not
confirmed is the only vulnerable one. The remaining findings (`pip`, `setuptools`, `cryptography`)
are in the local toolchain rather than anything this project declares.

If you need a guaranteed-clean dependency set, resolve it yourself and pin it; this project
deliberately keeps loose floors so it installs alongside other packages.

## Supported versions

This is an alpha research project; security fixes land on `main`. Pin a commit if you need stability.
