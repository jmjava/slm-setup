# Repository security scan — 2026-09-06

This is a public-safe record of secret and deployment-hygiene checks for
`jmjava/slm-setup`. No secret values are included.

## Full Git history

Tool: Gitleaks 8.30.1, downloaded from the official
[`gitleaks/gitleaks`](https://github.com/gitleaks/gitleaks) GitHub release.

Command shape:

```bash
gitleaks detect --source . --no-banner --redact --verbose
```

Result: **no leaks found** across 17 commits and approximately 160 KB of
scanned Git content.

## GitHub secret scanning

The GitHub secret-scanning alerts API returned an empty list for the
repository. No open or resolved alert metadata was present at scan time.

## Current tracked tree

Additional high-signal checks found:

- No private-key blocks.
- No AWS access-key patterns.
- No GitHub, OpenAI, Google, or Slack token patterns.
- No client-secret assignments containing a literal credential.
- No tracked `.env`; only `.env.example` is committed.
- No key-store, private-key, or credentials files.

Private-range IPv4 matches were limited to documented placeholders and unit
test fixtures. The repository's safety checker independently passed its
committed-address check.

## Deployment safety

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_deployment_safety.py
```

Result: **pass** while the local runtime was active:

- `OLLAMA_BASE_URL` resolved to loopback.
- Both configured model tags matched the documented official-library tags.
- `.env` was gitignored.
- No non-placeholder private address appeared in committed text.
- The configured Ollama port listened on loopback, not a wildcard interface.

## Limits

A clean secret scan reduces risk; it does not prove that no sensitive
information exists. Pattern scanners can miss novel credential formats,
encoded data, or sensitive prose. GitHub alert state can also change after
this dated check.

Ignored local files and model data were outside the Git-history scan. That is
intentional: `.env` and the local model store must remain untracked. Generated
model output still requires review even when the repository contains no
credentials.
