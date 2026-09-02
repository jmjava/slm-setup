# slm-setup

Public spec for a **local coding SLM** behind a **single MCP bridge**, used by
premium agents in Cursor, GitHub Copilot, and Claude Code.

The premium model plans and reviews. The local model does bounded, mechanical
generation on a private GPU host running [Ollama](https://ollama.com). No
OpenRouter (or other extra router) is required.

## Read this first

- **[spec.md](spec.md)** — architecture, routing rules, Ollama setup, and
  Cursor / Copilot / Claude Code adapters.
- **[examples/](examples/)** — public-safe client config templates. Copy them
  locally; put the real Ollama URL in your environment, not in git.

## What this repo is not

- Not a cloud model proxy.
- Not a guide for exposing Ollama on the public internet.
- Not ready-to-run MCP server code yet (that is the next slice after the spec).

## Quick mental model

```
IDE / CLI on the workstation
   premium agent  →  local-coding-slm MCP (stdio)
                         →  http://<inference-host>:11434
                              →  Ollama + local SLM
```

Workstation and inference host can be the same machine or two machines on a
private LAN.
