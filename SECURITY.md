# Security Policy

## Reporting a vulnerability

If you find a security issue — a secret-handling bug, an injection in the browser/MCP paths, an
unsafe-deserialization, a supply-chain concern, or anything that could harm a user running this tool —
please report it **privately**:

- Use GitHub's **[Report a vulnerability](https://github.com/ssamba1/humanize/security/advisories/new)**
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

## Supported versions

This is an alpha research project; security fixes land on `main`. Pin a commit if you need stability.
