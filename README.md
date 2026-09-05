# slm-setup

Public spec and **stdio MCP bridge** for a **local coding SLM**. Premium agents
in Cursor, GitHub Copilot, and Claude Code plan and review. The local model
does bounded, mechanical generation on a private GPU host running
[Ollama](https://ollama.com). No OpenRouter (or other extra router) is required.

## Read this first

- **[spec.md](spec.md)** — architecture, routing rules, Ollama setup, and
  Cursor / Copilot / Claude Code adapters.
- **[examples/](examples/)** — public-safe client config templates. Copy them
  locally; put the real Ollama URL in your environment, not in git.
- **[examples/downstairs-wsl-gpu.md](examples/downstairs-wsl-gpu.md)** —
  second GPU host in WSL over SSH, placeholders only.

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

6. Deployment safety checks (no GPU required; inspects this host only):

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/check_deployment_safety.py
   ```

7. Live acceptance for the MCP tools (needs Ollama + the fast model):

   ```bash
   .venv/bin/python scripts/prove_acceptance.py
   ```

Cursor loads `.cursor/mcp.json` (interpolation + `envFile` `.env`). Copilot
uses `.vscode/mcp.json`. Claude Code uses `.mcp.json`. Reload the client after
the first checkout so it picks up the server.

## Security

Keep Ollama on `127.0.0.1`. Prefer `ssh -L` to a second host instead of binding
`0.0.0.0`. Do not port-forward 11434. Do not commit `.env` or model stores.

Open-weight models are a privacy win, not an integrity guarantee. **Qwen** is a
model family (some tags are large LLMs). `qwen3.5:9b` is the starter SLM here.
Pull only official Ollama library tags. Unofficial GGUFs and one-off fine-tunes
are the usual way a trojaned SLM shows up. Treat every `local_*` result as
untrusted and review it before applying. The checker cannot see inside weights.

Details: [spec.md §12](spec.md#12-security).
