# Harness host plan

The measurement harness is `scripts/run_harness.py` and
`scripts/run_eval.py --live`. Both talk to whatever Ollama
`OLLAMA_BASE_URL` names. Moving the harness from one GPU to the next
is a loopback URL change on the workstation. The MCP tool names stay
`local_*`. Cursor still chooses accept, rewrite, or reject before a
result is copied into the repo. Live output goes under gitignored
`eval-runs/`.

Phase 3 timings stay on the downstairs forward
([examples/downstairs-wsl-gpu.md](../examples/downstairs-wsl-gpu.md),
workstation port `11436`). This page is the personal link: the
4080-class cards first, the Ryzen AI Max+ 395 after that link has a
fast-model row.

## Ports

One URL is active in `.env` at a time. The forwards can all be up.
Ollama on each GPU host stays on `127.0.0.1:11434`. These workstation
ports are examples; pick any free loopback port and write it only in
`.env`.

| Host | Workstation `OLLAMA_BASE_URL` | How it gets there |
| --- | --- | --- |
| IDE 4080-class card, Ollama on this machine | `http://127.0.0.1:11434` | Direct loopback |
| Another 4080-class machine | `http://127.0.0.1:11438` | `ssh -L 127.0.0.1:11438:127.0.0.1:11434` |
| Downstairs paper host | `http://127.0.0.1:11436` | Existing downstairs forward |
| Ryzen AI Max+ 395 | `http://127.0.0.1:11440` | `ssh -L 127.0.0.1:11440:127.0.0.1:11434` |

A second 4080 uses the same steps as the first, with its own port and
its own `eval-runs/` directory. The harness has no host flag.

Workers that speak Aider's client set `OLLAMA_API_BASE` to that same
loopback URL for the session. The MCP harness itself reads
`OLLAMA_BASE_URL`.

## Plan 1 — 4080-class NVIDIA

Do this on the IDE card before pointing the harness at the 395.

On the 4080 host:

1. Install a current Ollama. Leave it on `127.0.0.1:11434`.
2. Pull the starter pair from the Ollama library:
   `qwen3.5:9b`, then `devstral-small-2`.
3. Run one short chat on the fast tag and read `ollama ps`.
   The fast tag should sit on the GPU. The strong tag is about 15 GB
   and sits at the edge of 16 GB, so leave it idle until the fast
   link is green. Keep `OLLAMA_NUM_CTX=16384`.

On the workstation, with `.env` pointing at that host's loopback port:

```bash
curl -fsS "$OLLAMA_BASE_URL/api/tags"
python scripts/check_deployment_safety.py
PYTHONPATH=src python scripts/run_eval.py --live --model fast --case whitespace_extract
PYTHONPATH=src python scripts/run_harness.py --backend live \
  --case whitespace_extract --out eval-runs/ide-4080-fast
```

A remote 4080 uses the same four commands after:

```bash
ssh -N -T -o ExitOnForwardFailure=yes -p <ssh-port> \
  -L 127.0.0.1:11438:127.0.0.1:11434 user@<4080-host>
```

`<4080-host>` and `<ssh-port>` stay in the gitignored `.env` notes.
`user@4080-private-host.example` is a documentation stand-in.

Record, in `eval-runs/` or a gitignored local note:

- host label `ide-4080` or `4080-remote`
- `ollama ps` placement (GPU, CPU, or split)
- the case id, model role, pass/fail, and `first_failure`
- `mcp_ms` from the harness JSONL

When the fast case passes and `ollama ps` shows `qwen3.5:9b` on the
GPU, run one strong case:

```bash
PYTHONPATH=src python scripts/run_eval.py --live --model strong --case whitespace_extract
```

Read `ollama ps` again. A split placement on the strong tag means the
next personal runs stay on the fast tag until the card holds the
strong tag with `OLLAMA_NUM_CTX=16384`. A full strong corpus waits
for that reading.

Phase 3's downstairs series stays in `docs/phase3-log.md`. Personal
4080 rows stay in `eval-runs/`.

## Plan 2 — Ryzen AI Max+ 395

Start this after Plan 1 has a fast-model live row, and after the
395 is in the lab. Downstairs keeps port `11436`. The 395 uses
`11440`, so the paper forward can stay up while you try the new box.

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
desktop MCP client, and run the deployment checker. Then the same
harness commands, with a different output directory:

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
same score fields as Plan 1. Starter-tag rows come first. A larger
official library tag waits until those rows exist and you have written
down peak unified memory for the starter pair at 16384 context.

Phase 4 is claimed when A13 is green and downstairs is already
measuring, which is the order in [roadmap.md](roadmap.md). The
harness command does not change when that happens.

## After either host

`scripts/check_deployment_safety.py` after every `.env` edit.
A loopback URL passes. A public or tunnel URL fails. A private LAN
URL warns; the SSH forward above avoids that warning.

The harness scores the local text. It does not merge. Copy a hunk
back only after Cursor's accept, rewrite, or reject.
