# slm-setup

Public spec and **stdio MCP bridge** for a **local coding SLM**. Premium agents
in Cursor, GitHub Copilot, and Claude Code plan and review. The local model
does bounded, mechanical generation on a private GPU host running
[Ollama](https://ollama.com). No OpenRouter (or other extra router) is required.

## Status (2026-09-04)

The local same-machine lab is running. Phase 1 (Ollama + starter models) and
Phase 2 (stdio MCP server) are in this repo. A second GPU host on the LAN is
not wired yet. Cloud agents stay unsupported.

| Check | State |
| --- | --- |
| A1 tags list fast + strong models | Done on localhost |
| A2 fast-model chat, GPU visible | Done |
| A3 strong-model chat | Done (GPU or GPU+RAM is allowed) |
| A4 LAN bind / second machine | Skipped (same-machine lab) |
| A5 `local_status` | Done |
| A6 `local_generate_tests` | Done |
| A7 Cursor Agent calls a `local_*` tool | Done |
| A8 Copilot Agent | Not run |
| A9 Claude Code local | Not run |
| A10 Cloud agents | Unsupported by design |
| A11 no private IPs / emails in git | Done |

Project MCP now starts `scripts/run_mcp.sh`, which finds the repo from the
script path and loads `.env`. Empty `${env:NAME}` interpolations no longer
block the real URL. User MCP config remains a fallback. Keep the real
`OLLAMA_BASE_URL` out of git.

Draft PR: [jmjava/slm-setup#2](https://github.com/jmjava/slm-setup/pull/2).

## Read this first

- **[spec.md](spec.md)** — architecture, routing rules, Ollama setup, and
  Cursor / Copilot / Claude Code adapters.
- **[examples/](examples/)** — public-safe client config templates. Copy them
  locally; put the real Ollama URL in your environment, not in git.

## What this repo is not

- Not a cloud model proxy.
- Not a guide for exposing Ollama on the public internet.
- Not a Cursor "Override OpenAI Base URL" setup. Keep premium models as-is and
  call the local SLM as MCP tools.

## Quick mental model

```
IDE / CLI on the workstation
   premium agent  →  local-coding-slm MCP (stdio)
                         →  http://<inference-host>:11434
                              →  Ollama + local SLM
```

Workstation and inference host can be the same machine or two machines on a
private LAN.

## Local lab (same machine)

1. Install a current [Ollama](https://ollama.com/download) binary. Distro
   packages can be too old for the starter tags.
2. Copy `.env.example` to `.env`. Same-machine default is
   `http://127.0.0.1:11434`. If you run a second local Ollama (for example a
   newer user-local binary), point `OLLAMA_BASE_URL` at that listener only.
3. Pull the starter models:

   ```bash
   ollama pull qwen3.5:9b
   ollama pull devstral-small-2
   ```

4. Create a venv and install the MCP server:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e .
   ```

5. Unit tests (no GPU required):

   ```bash
   PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
   ```

6. Live acceptance for the MCP tools (needs Ollama + the fast model):

   ```bash
   .venv/bin/python scripts/prove_acceptance.py
   ```

Cursor loads `.cursor/mcp.json`, which runs `scripts/run_mcp.sh`. Copilot
uses `.vscode/mcp.json`. Claude Code uses `.mcp.json`. Reload the client after
the first checkout so it picks up the server. Informal Phase 3 notes go in
`docs/phase3-log.md`.

## Security

Keep Ollama on localhost or a private LAN. Do not port-forward it. Do not
commit `.env` or model stores.
