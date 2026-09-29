# Roadmap

Planning index only. Architecture and acceptance tests stay in
[spec.md](../spec.md). C4 views: [c4.md](c4.md). Do not put hostnames,
LAN addresses, or SKUs here.

## Current line

| Phase | Status | What it is |
| --- | --- | --- |
| 1 — inference host | Done on the workstation lab | Ollama + starter tags on a private GPU |
| 2 — MCP bridge | Done | `local-coding-slm` stdio tools; Cursor / Copilot / Claude adapters |
| 3 — measure | Protocol + corpus + apply gate + CI; **live rates still need a stable remote GPU** | Layered scoring; next live rows go through downstairs |
| **T12 Part A downstairs** | **Next hardware work** (early Nov 2026) | Second PC / WSL NVIDIA via SSH — was blocked on host power; [examples/downstairs-wsl-gpu.md](../examples/downstairs-wsl-gpu.md) |
| T12 Part B Copilot A8 / Claude A9 | Config ready; operator clicks pending | Same-machine only; do not block on downstairs; [docs/a8-a9-operator-checklist.md](a8-a9-operator-checklist.md) |

**Order (do not invert):** finish Phase 3 live measurement on **downstairs** (T12 Part A) **before** treating Halo as the next lab.

1. **First work — downstairs:** power on, WSL Ollama, `ssh -L` from the IDE workstation, A4-class check, scrubbed live harness / `run_eval.py --live` rows.
2. **Then — keep measuring** Part A on downstairs through November.
3. **Later — Halo / 395** (~Black Friday): bring-up and A13 only after downstairs is a known path (on, or explicitly abandoned).

Public-safe downstairs notes:
[examples/downstairs-wsl-gpu.md](../examples/downstairs-wsl-gpu.md).

**Halo / Ryzen AI Max+ 395:** planned acquire around **Black Friday week Nov 2026**.
Claim Phase 4 only after A13. Until then Phase 3 live rates stay on **downstairs**, not workstation-local Ollama and not Halo. Paper track:
[embabel-slm paper calendar](https://github.com/jmjava/embabel-slm/blob/main/docs/paper-calendar-2026.md).

Paper track: Nov 2026–Mar 2027 Zenodo preprint (DOI by **31 Mar 2027**). Live
`pass@1` / `pass@end` freeze by early January (**downstairs** default; Halo only if
A13 green); all paper numbers freeze by late February.

## Phase 4 — Halo host profile (planned ~Black Friday Nov 2026)

Use an AMD Ryzen AI Max+ 395 / Halo-class box as **another private Ollama host**.
Target arrival: **around Black Friday week November 2026**. The MCP server stays
on the workstation. Premium agents still plan and review.

Until the box exists and A13 passes, do not claim this phase — keep Phase 3 live
rates on the **downstairs** host (T12 Part A). Do not skip downstairs to chase Halo.

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
   `ssh -N -T -o ExitOnForwardFailure=yes
   -L 127.0.0.1:11436:127.0.0.1:11434 user@<halo-host>` and keep Ollama on
   Halo localhost. Use any unused workstation port in place of `11436`.
   A private-interface bind plus a workstation-only firewall is optional.
4. Point gitignored `.env` at `http://127.0.0.1:11436`. Reload desktop MCP.
   Re-run
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
- Cloud-agent access to the private GPU in this home-lab profile
- A second MCP server just for Halo
