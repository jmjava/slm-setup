# Harness host plan

The measurement harness is `scripts/run_harness.py` and
`scripts/run_eval.py --live`. Both talk to whatever Ollama
`OLLAMA_BASE_URL` names. Moving the harness from one GPU to the next
is a loopback URL change on the workstation. The MCP tool names stay
`local_*`. Cursor still chooses accept, rewrite, or reject before a
result is copied into the repo. Live output goes under gitignored
`eval-runs/`.

**25 Nov 2026:** Phase 3 paper timings run on the **Halo / GEEKOM 395**
forward ([examples/halo-ryzen-ai.md](../examples/halo-ryzen-ai.md)).
Downstairs NVIDIA and IDE 4080-class cards are fallback or personal
smoke only. Do not mix `host_class` values in one average.

## Ports

One URL is active in `.env` at a time. The forwards can all be up.
Ollama on each GPU host stays on `127.0.0.1:11434`. These workstation
ports are examples; pick any free loopback port and write it only in
`.env`.

| Host | Workstation `OLLAMA_BASE_URL` | How it gets there |
| --- | --- | --- |
| Ryzen AI Max+ 395 (paper) | `http://127.0.0.1:11440` | `ssh -L 127.0.0.1:11440:127.0.0.1:11434` |
| Downstairs fallback | `http://127.0.0.1:11436` | Existing downstairs forward |
| IDE 4080-class card, Ollama on this machine | `http://127.0.0.1:11434` | Direct loopback (not paper) |
| Another 4080-class machine | `http://127.0.0.1:11438` | `ssh -L 127.0.0.1:11438:127.0.0.1:11434` |

A second 4080 uses the same steps as the first, with its own port and
its own `eval-runs/` directory. The harness has no host flag.

Workers that speak Aider's client set `OLLAMA_API_BASE` to that same
loopback URL for the session. The MCP harness itself reads
`OLLAMA_BASE_URL`.

## Plan 1 — Halo / Ryzen AI Max+ 395 (paper host)

This is the default path for Phase 3 live rows and Embabel inference.

On the 395:

1. Bring up a current Ollama with the AMD backend that box actually
   runs. Write down whether that backend is ROCm or Vulkan.
2. Pull `qwen3.5:9b` and `devstral-small-2`. Confirm accelerated
   placement with `ollama ps` after one short fast chat.
   That reading is acceptance A13.
3. Leave Ollama on `127.0.0.1:11434`.

On the workstation:

```bash
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:11440:127.0.0.1:11434 user@<395-host>
```

Set `OLLAMA_BASE_URL=http://127.0.0.1:11440` in `.env`, reload the
desktop MCP client, and run the deployment checker. Then:

```bash
curl -fsS "$OLLAMA_BASE_URL/api/tags"
python scripts/check_deployment_safety.py
PYTHONPATH=src python scripts/run_eval.py --live --model fast --case whitespace_extract
PYTHONPATH=src python scripts/run_harness.py --backend live \
  --case whitespace_extract --out eval-runs/halo-395-fast
```

`<395-host>` is a placeholder. `user@halo-private-host.example` is
the documentation stand-in. Public-safe Halo notes:
[examples/halo-ryzen-ai.md](../examples/halo-ryzen-ai.md).

Record host label `halo-395`, the backend name, `ollama ps`, and the
score fields. Starter-tag rows come first. A larger official library
tag waits until those rows exist and you have written down peak unified
memory for the starter pair at 16384 context.

Phase 4 is claimed when A13 is green ([roadmap.md](roadmap.md)). The
harness command does not change when that happens.

## Plan 2 — Downstairs / 4080-class fallback

Use this only if Halo cannot place starter tags on the 8060S-class GPU,
or for a deliberate paired host study. Prefer 4080-class over 3060.

On the NVIDIA host:

1. Install a current Ollama. Leave it on `127.0.0.1:11434`.
2. Pull the starter pair: `qwen3.5:9b`, then `devstral-small-2`.
3. Run one short chat on the fast tag and read `ollama ps`.

On the workstation, with `.env` pointing at that host's loopback port:

```bash
curl -fsS "$OLLAMA_BASE_URL/api/tags"
python scripts/check_deployment_safety.py
PYTHONPATH=src python scripts/run_eval.py --live --model fast --case whitespace_extract
PYTHONPATH=src python scripts/run_harness.py --backend live \
  --case whitespace_extract --out eval-runs/downstairs-4080-fast
```

A remote host uses the same four commands after:

```bash
ssh -N -T -o ExitOnForwardFailure=yes -p <ssh-port> \
  -L 127.0.0.1:11436:127.0.0.1:11434 user@<4080-host>
```

Record `host_class=downstairs-4080` (or `downstairs-3060` / `ide-4080`).
Never average these timings with `halo-395` rows.

## After either host

`scripts/check_deployment_safety.py` after every `.env` edit.
A loopback URL passes. A public or tunnel URL fails. A private LAN
URL warns; the SSH forward above avoids that warning.

The harness scores the local text. It does not merge. Copy a hunk
back only after Cursor's accept, rewrite, or reject.
