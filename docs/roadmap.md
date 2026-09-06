# Roadmap

Planning index only. Architecture and acceptance tests stay in
[spec.md](../spec.md). C4 views: [c4.md](c4.md). Do not put hostnames,
LAN addresses, or SKUs here.

## Current line

| Phase | Status | What it is |
| --- | --- | --- |
| 1 — inference host | Done on the workstation lab | Ollama + starter tags on a private GPU |
| 2 — MCP bridge | Done | `local-coding-slm` stdio tools; Cursor / Copilot / Claude adapters |
| 3 — measure | Informal log started | Success rate, latency, escalation; no auto-classifier yet |
| T12 second NVIDIA host | Blocked on host power | WSL GPU via SSH; see [examples/downstairs-wsl-gpu.md](../examples/downstairs-wsl-gpu.md) |

Finish Phase 3 measurement and the existing second-host checks before treating
Halo as the next lab.

## Phase 4 — Halo host profile (future)

Use an AMD Ryzen AI Halo-class box as **another private Ollama host**. The
MCP server stays on the workstation. Premium agents still plan and review.

This is **not** a second product. It is the same bridge with a different
`OLLAMA_BASE_URL` (or the same loopback URL behind `ssh -L`).

Public-safe notes: [examples/halo-ryzen-ai.md](../examples/halo-ryzen-ai.md).

### Already satisfied (do not redo)

- Stdio MCP on the workstation; no listening port
- Tools: `local_status`, `local_code`, `local_refactor`,
  `local_generate_tests`, `local_explain`, `local_review`
- Env contract: `OLLAMA_BASE_URL`, `OLLAMA_FAST_MODEL`,
  `OLLAMA_STRONG_MODEL`, `OLLAMA_NUM_CTX`
- Starter tags: `qwen3.5:9b` / `devstral-small-2`
- No public tunnels; cloud agents out of scope
- Official Ollama library tags only; output treated as untrusted
- Deployment checker (`A12`)

### Halo-specific work (when the box exists)

1. Validate current Ollama on the Halo with its supported AMD backend; record
   whether ROCm or Vulkan is used. Confirm accelerated placement after a short
   chat before selecting larger models.
2. Pull the starter pair. Leave larger coding tags for a later benchmark.
3. Reach the API from the workstation. Prefer
   `ssh -L 11434:127.0.0.1:11434` and keep Ollama on Halo localhost.
   A private-interface bind plus a workstation-only firewall is optional.
4. Point gitignored `.env` at that URL. Reload desktop MCP. Re-run
   `scripts/check_deployment_safety.py`.
5. Repeat acceptance **A1–A7** and **A11–A12**. Run **A4** (the workstation
   succeeds through SSH; an unauthorized LAN client fails). **A8/A9** only if
   those clients are in use.
6. After the starter pair feels usable, record a Halo benchmark
   (model + quant, effective context, tok/s, time to first token,
   peak unified memory, whether output is reviewable). Do not treat a
   large advertised context window as a reason to send the whole repo.

### Explicit non-changes

- Do not rename tools to `write_code` / `ollama_status`. `local_*` is the
  contract already in Cursor, Copilot, and Claude configs.
- Do not add `SLM_*` environment aliases unless a later consumer cannot
  use `OLLAMA_*`.
- Do not expose Halo in Cursor's model picker.
- Do not implement an automatic task classifier (still Phase 3).
- Do not start Halo install or wrapper changes until this phase is
  claimed.

### Optional hardening (only if Halo work shows the gap)

These are **not** required to start Phase 4. Schedule them if the Halo
path needs them:

- Wrapper preflight: reject a non-private `OLLAMA_BASE_URL` and fail
  clearly when `/api/tags` is down (no public fallback).
- Reject oversized tool payloads (`files` + `task` over a configured
  character cap).
- Keep dual fast/strong timeouts; a single `SLM_TIMEOUT_SECONDS` is
  unnecessary unless operators ask for one knob.

## Later than Phase 4

- Automatic routing / classifiers (only after Phase 3 numbers exist)
- Larger-than-starter models on Halo unified memory
- Application-level shared secret, only if Ollama can do it without
  breaking local IDE use

## Out of scope (unchanged)

- OpenRouter or Cursor OpenAI-base-URL override
- Public Ollama, ngrok, Cloudflare Tunnel
- Cloud-agent access to the private GPU
- A second MCP server just for Halo
