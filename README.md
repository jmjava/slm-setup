# slm-setup

Public spec and **stdio MCP bridge** for a **local coding SLM**. Premium agents
in Cursor, GitHub Copilot, and Claude Code plan and review. The local model
does bounded, mechanical generation on a private GPU host running
[Ollama](https://ollama.com). No OpenRouter (or other extra router) is required.

## Read this first

- **[spec.md](spec.md)** — architecture, routing rules, Ollama setup, and
  Cursor / Copilot / Claude Code adapters.
- **[docs/roadmap.md](docs/roadmap.md)** — current phases and the future
  Halo host profile (planning only).
- **[docs/c4.md](docs/c4.md)** — C4 context, container, and component
  diagrams (Halo is the same containers, a later host).
- **[docs/local-acceptance-results-2026-09-06.md](docs/local-acceptance-results-2026-09-06.md)**
  — dated unit, live MCP, and semantic-refactor results with limitations.
- **[docs/evaluation-protocol.md](docs/evaluation-protocol.md)** — layered
  scoring (transport / format / structure / behavior) and the committed
  fixture corpus. Cloud Agents can run the fixtures; live Ollama stays on
  the workstation.
- **[docs/cloud-orchestrator-results-2026-09-07.md](docs/cloud-orchestrator-results-2026-09-07.md)**
  — dated Cloud Agent run of the stub corpus and apply gate (no GPU).
- **[docs/security-scan-results-2026-09-06.md](docs/security-scan-results-2026-09-06.md)**
  — dated Gitleaks, GitHub alert, tracked-tree, and deployment-safety results.
- **[examples/](examples/)** — public-safe client config templates. Copy them
  locally; put the real Ollama URL in your environment, not in git.
- **[examples/downstairs-wsl-gpu.md](examples/downstairs-wsl-gpu.md)** —
  second GPU host in WSL over SSH, placeholders only.
- **[examples/halo-ryzen-ai.md](examples/halo-ryzen-ai.md)** — future
  AMD Halo-class Ollama host, placeholders only.
- **[docs/a8-a9-operator-checklist.md](docs/a8-a9-operator-checklist.md)** —
  Copilot A8 / Claude A9 clicks. Config in git is not a pass.

## What this repo is not

- Not a cloud model proxy.
- Not a guide for exposing Ollama on the public internet.
- Not a Cursor "Override OpenAI Base URL" setup. Keep premium models as-is and
  call the local SLM as MCP tools.

## Quick mental model

```
IDE / CLI on the workstation
   premium agent  →  local-coding-slm MCP (stdio)
                         →  local Ollama URL
                            (direct localhost or SSH local forward)
                              →  Ollama + local SLM
```

Workstation and inference host can be the same machine or two private machines
connected through SSH local forwarding.

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

5. Unit tests (no GPU required; Ollama HTTP calls are mocked; the eval
   corpus is scored from committed fixtures):

   ```bash
   PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
   .venv/bin/python scripts/run_eval.py
   .venv/bin/python scripts/prove_multifile_refactor.py
   .venv/bin/python scripts/run_harness.py --backend stub --profile observed --out eval-runs/observed
   .venv/bin/python scripts/run_orchestration.py
   .venv/bin/python scripts/run_harness.py --backend stub --profile golden --orchestrate
   ```

   GitHub Actions (`.github/workflows/tests.yml`) runs the same no-GPU path
   on push and pull request.

6. Deployment safety checks (no GPU required; inspects this host only):

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/check_deployment_safety.py
   ```

7. Live acceptance for MCP discovery, status, and test generation (needs the
   configured Ollama runtime and fast model):

   ```bash
   .venv/bin/python scripts/prove_acceptance.py
   ```

8. Live semantic refactor acceptance (calls the real `local_refactor`, parses
   and executes its generated module, and checks behavior preservation):

   ```bash
   .venv/bin/python scripts/prove_refactor_acceptance.py --model fast
   .venv/bin/python scripts/prove_refactor_acceptance.py --model strong
   ```

   Harder multi-file cases (exception rename, dataclass field rename, tuple
   return + facade) are offline by default. `--live` skips with exit 0 when
   Ollama is down; that skip is not a quality pass:

   ```bash
   .venv/bin/python scripts/prove_multifile_refactor.py
   .venv/bin/python scripts/prove_multifile_refactor.py --live --model fast
   ```

The unit suite proves deterministic client, safety, evaluation-scorer,
and harness behavior. The live acceptance scripts are the evidence that the
stdio MCP server can reach the configured Ollama runtime and produce usable
output; do not describe the unit suite as exercising Ollama. Layered scoring,
the fixture corpus, and the stub/live harness:
[evaluation protocol](docs/evaluation-protocol.md). See the dated
[local acceptance results](docs/local-acceptance-results-2026-09-06.md)
for observations, retries, and limits on what these checks establish.

Cursor loads `.cursor/mcp.json` (interpolation + `envFile` `.env`). Copilot
uses `.vscode/mcp.json` (VS Code Agent) or
[`examples/copilot-cli.mcp.json`](examples/copilot-cli.mcp.json) copied to
`~/.copilot/mcp-config.json` with a local clone path. Claude Code uses
`.mcp.json`. Reload the client after the first checkout so it picks up the
server. Copilot A8 and Claude A9 still need the operator clicks in
[docs/a8-a9-operator-checklist.md](docs/a8-a9-operator-checklist.md).

## Security

Keep Ollama on `127.0.0.1`. Prefer an explicit workstation-only SSH forward to
a second host instead of binding Ollama to `0.0.0.0`:

```bash
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:11436:127.0.0.1:11434 user@<inference-host>
```

Then set `OLLAMA_BASE_URL=http://127.0.0.1:11436` locally. Port `11436` is an
example unused workstation port; remote Ollama remains on `11434`. Do not
create a public tunnel or router port-forward. Do not commit `.env` or model
stores.

Open-weight models are a privacy win, not an integrity guarantee. **Qwen** is a
model family (some tags are large LLMs). `qwen3.5:9b` is the starter SLM here.
Pull only official Ollama library tags. Unofficial GGUFs and one-off fine-tunes
are the usual way a trojaned SLM shows up. Treat every `local_*` result as
untrusted and review it before applying. The checker cannot see inside weights.

Details: [spec.md §12](spec.md#12-security).
