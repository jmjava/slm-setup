# Local coding SLM + MCP bridge

Public specification for running a small local coding model on a private
inference host and exposing it to premium coding agents as **tools**, not as
another cloud model.

This document is intentionally generic. It does not include personal hostnames,
LAN addresses, usernames, or hardware serials. Those values stay in local
environment files that are never committed.

---

## 1. Purpose

Use a premium agent (Cursor, GitHub Copilot, or Claude Code) as the
**orchestrator**. Use a local SLM on a private GPU host as **cheap, bounded
generation capacity**.

Typical split:

| Task class | Owner |
| --- | --- |
| Planning, architecture, ambiguous debugging, multi-system diagnosis | Premium agent |
| Boilerplate, tests, mechanical refactors, summaries, explanations | Local SLM via MCP |
| Local answer looks wrong or incomplete | Premium agent reviews / retries |

The goal is not to replace the premium subscription. The goal is to stop
spending premium tokens on repetitive generation that a 9B–24B local model can
handle.

OpenRouter and other third-party routers are **out of scope**. Premium models
come from the agent product itself (Cursor Ultra / included models, Copilot,
Claude).

---

## 2. Design principles

1. **One MCP implementation, three front ends.** Cursor, Copilot, and Claude
   Code all call the same local tool server.
2. **Keep the inference host private.** Prefer Ollama on `127.0.0.1` and reach
   a second host with `ssh -L`. Do not port-forward 11434 through a public
   router. Do not put Ollama on the internet.
3. **Do not point Cursor at Ollama as a model provider.** Cursor's normal model
   selector and "Override OpenAI Base URL" path go through Cursor's servers, so
   a private `http://<lan-host>:11434` endpoint is not reachable. A local MCP
   process on the workstation *can* reach that LAN URL.
4. **Public-repo safe.** Committed files use placeholders and environment
   variable expansion. Real IPs, hostnames, and tokens live in `.env` or the
   user environment.
5. **Start simple.** Measure whether the local model is good enough before
   adding automatic classifiers, retries, or cost dashboards.

---

## 3. Architecture

```
Cursor premium  ────┐
Copilot premium ────┼──> local-coding-slm MCP (stdio on the workstation)
Claude premium  ────┘             │
                                  │ private LAN / localhost
                                  ▼
                           Ollama HTTP API
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
              fast SLM                   stronger SLM
           (everyday coding)         (harder coding tasks)
```

| Role | What it is | What it is not |
| --- | --- | --- |
| **Workstation** | Machine running the IDE / CLI. Hosts the MCP server. | Does not need to load the model. |
| **Inference host** | Machine that runs Ollama (NVIDIA GPU now; Halo-class AMD later). | Does not need the IDE installed. |
| **Premium agent** | Plans, reads the repo, calls MCP tools, reviews output. | Does not talk to Ollama directly. |
| **Local SLM** | Generates bounded artifacts (tests, diffs, explanations). | Does not own repository context or tool use in the IDE. |

Workstation and inference host may be the same computer. They may also be two
machines on one private network. The MCP server only needs an HTTP URL.

C4 context, container, component, and deployment-variant diagrams:
[docs/c4.md](docs/c4.md).

---

## 4. Hardware assumptions (generic)

These are sizing guidelines, not a shopping list and not a description of any
specific machine.

| Component | Recommended starting point |
| --- | --- |
| Inference GPU | NVIDIA GPU with **16 GB VRAM** is enough for the starter models below |
| Inference system RAM | **32–64 GB** is plenty; extra RAM helps offload, not interactive speed |
| Workstation | Any machine that can run the IDE and reach the inference host over LAN |
| Network | Private Ethernet or Wi-Fi. Gigabit is more than enough (prompts/tokens only) |
| OS on inference host | Windows, Linux, or macOS. Ollama is first-class on all three. Dual-boot is not required. |

VRAM is the scarce resource. System RAM offload can *load* a larger model; it
does not make it feel fast for interactive coding.

Rough fit on a 16 GB GPU:

| Model class | Typical quantized size | Expected fit | Use |
| --- | --- | --- | --- |
| ~8–9B Q4 | ~6–8 GB | Fully in VRAM with context headroom | Fast everyday coding |
| ~14B Q4 | ~8–10 GB | Fully / nearly fully in VRAM | Strong local coding |
| ~24B Q4 | ~15 GB | At the VRAM edge; some RAM offload possible | Harder agentic / multi-file work |
| 30B+ Q4 | 18 GB+ | Offload required | Usable but often too slow |

Context windows consume extra VRAM. Start at **16K–32K** tokens even if a model
advertises 256K.

### Worked example: RTX 4080 Super + 64 GB RAM

An RTX 4080 Super has **16 GB VRAM**. With **64 GB** system RAM it matches the
recommended starting point above. VRAM is still the limit. Extra RAM only
helps if a model spills off the GPU, and that spill is usually too slow for
interactive coding.

On this class of card, install the same starter pair as §5:

| Role | Tag | Why it fits |
| --- | --- | --- |
| Fast | `qwen3.5:9b` (~6.6 GB) | Fully on GPU, room for 16K context |
| Strong | `devstral-small-2` (~15 GB) | At the 16 GB edge; keep `OLLAMA_NUM_CTX=16384` |

Install both. Default to the 9B. Escalate to Devstral only when the agent
needs multi-file work.

Do **not** start with 30B+ Q4 on this card. Those need offload and will feel
worse than Devstral in VRAM. Later, if Devstral is fully resident and you
want more, try a ~14B Q4 coding tag — not a 30B.

### Future host profile: Halo-class AMD

A later inference host may be an AMD Ryzen AI Halo-class APU (unified
memory, ROCm, Ollama). That does **not** change the MCP contract. The
workstation still runs `local-coding-slm`; only `OLLAMA_BASE_URL` (or an
SSH local-forward to the same loopback URL) changes.

Do not start that lab until Phase 3 measurement and the existing second
NVIDIA host are in a known state. Planning index:
[docs/roadmap.md](docs/roadmap.md). Public-safe notes:
[examples/halo-ryzen-ai.md](examples/halo-ryzen-ai.md).

On Halo, treat unified memory the same way this spec treats VRAM: start
at **16K–32K** context and the starter pair. A large advertised window is
not permission to send the repository.

---

## 5. Starter models

Treat tags as a starting point. Confirm current names and sizes on
[ollama.com/library](https://ollama.com/library) before installing.

| Role | Suggested Ollama tag | Approx. download | Why |
| --- | --- | --- | --- |
| Fast | `qwen3.5:9b` | ~6.6 GB | Everyday coding; leaves VRAM for context on a 16 GB GPU |
| Strong | `devstral-small-2` | ~15 GB | Software-engineering / multi-file work; near 16 GB VRAM |

Install both. Use the fast model by default. Escalate to the strong model only
when the premium agent decides the task needs it.

Later candidates (not first experiments) include larger Qwen coding models
whose Q4 weights exceed 16 GB VRAM. On a 16 GB card such as an RTX 4080
Super, stay on the starter pair first; see the worked example in §4.

Environment variables (never commit real values if they encode a private host):

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_FAST_MODEL=qwen3.5:9b
OLLAMA_STRONG_MODEL=devstral-small-2
OLLAMA_NUM_CTX=16384
```

When the inference host is a second machine, set `OLLAMA_BASE_URL` to
`http://<inference-host>:11434` on the workstation only.

---

## 6. Why MCP instead of a model-provider override

### Cursor

Cursor can use custom OpenAI-compatible endpoints via **Override OpenAI Base
URL**. Those requests are assembled on Cursor's servers. A private LAN or
`localhost` Ollama URL is therefore not reachable unless it is published as a
public HTTPS endpoint.

Cursor also has a **single** OpenAI base-URL override. Pointing it at Ollama
fights with Cursor-native premium models.

**Do not use that path for this project.** Keep Cursor Ultra / included premium
models as-is. Add the local SLM as MCP tools.

### GitHub Copilot

Copilot Agent in the IDE can call **local stdio MCP servers**. That is the
supported equivalent: premium Copilot orchestrates, local tools generate.

Copilot **cloud agent** (the GitHub-hosted agent that opens PRs from issues)
runs on GitHub's runners. It cannot reach a private LAN Ollama host. Do not
configure this MCP server in repository Copilot cloud-agent settings.

### Claude Code

Claude Code supports local **stdio** MCP servers and project-scoped `.mcp.json`
with `${VAR}` / `${VAR:-default}` expansion. That is the supported equivalent.

Claude Code cloud / remote sessions also cannot see a private LAN host. Use
this bridge from a local Claude Code session on the workstation.

---

## 7. Shared MCP tool contract

Server name: `local-coding-slm`

Transport: **stdio** on the workstation. The server process calls Ollama over
HTTP. Do not expose the MCP server itself on the public internet.

All tools return plain text (generated code, unified diff, or markdown). The
premium agent decides whether to apply edits.

### Common input fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `task` | string | yes | What to produce. Bounded input. |
| `files` | array of `{ path, content }` | no | Snippets the premium agent chooses to send. Not a full-repo dump. |
| `language` | string | no | Hint, e.g. `java`, `typescript`. |
| `style` | string | no | Short conventions: test framework, naming, etc. |
| `model` | `fast` \| `strong` | no | Default `fast`. |
| `max_tokens` | integer | no | Server enforces an upper bound. |

Keep payloads small. The premium agent already has repository context. Send
only the files the SLM needs.

### Tools

| Tool | Purpose | Typical caller prompt |
| --- | --- | --- |
| `local_code` | Generate new code for a well-specified unit of work | "Write a health controller matching this existing style." |
| `local_refactor` | Mechanical, localized rewrite | "Rename this DTO field and update getters." |
| `local_generate_tests` | Unit / integration test bodies | "Add tests for these 12 services." |
| `local_explain` | Explain a snippet or flow | "What does this filter chain do?" |
| `local_review` | Cheap first-pass review | "Flag obvious null / auth / test gaps." |
| `local_status` | Health of Ollama + listed models | Used by acceptance tests and troubleshooting. |

### Tool behavior

- Call `POST {OLLAMA_BASE_URL}/api/chat` with `stream: false`.
- Map `model=fast|strong` to `OLLAMA_FAST_MODEL` / `OLLAMA_STRONG_MODEL`.
- Pass `options.num_ctx` from `OLLAMA_NUM_CTX` (default 16384).
- Time out (suggested 120s fast / 300s strong) and return a structured error.
- Never execute shell commands, never write files, never open network ports
  other than the configured Ollama URL.
- Redact nothing special in committed code; do not log full prompts to disk by
  default.

### System prompts (server-side)

Each tool uses a short, fixed system prompt. The premium agent supplies the
user task. Example for `local_generate_tests`:

```
You generate tests only. Match the language and framework hinted in the
request. Do not invent production code changes. Return files as markdown
fenced blocks with path comments, or a unified diff. If the request is
ambiguous, ask up to three clarifying questions instead of guessing.
```

---

## 8. Routing rules

These rules are for the **premium agent**, not for a separate classifier
service (phase 1). Put a short copy in each client's project instructions
(see §10).

```
Mechanical / repetitive / well-specified  →  local_* tools (fast, then strong)
Ambiguous / architectural / multi-system  →  premium model only
Local answer incomplete or wrong          →  premium model reviews
```

Delegate when **all** of these are true:

- The output shape is obvious (tests, boilerplate, rename, summary).
- The needed context fits in a few files.
- A wrong answer is cheap to reject.

Do **not** delegate:

- Incident / race / auth debugging across systems.
- Broad refactors with unclear invariants.
- Security-sensitive code without premium review.
- Anything that needs live repo tools (search, terminal, browser) the SLM
  does not have.

The premium model will still spend some tokens deciding and reviewing. That is
expected. Savings come from not using it to emit thousands of lines of
mechanical code.

---

## 9. Inference host: Ollama

Official install: [https://ollama.com/download](https://ollama.com/download)

### 9.1 Install models

```bash
ollama run qwen3.5:9b
ollama run devstral-small-2
```

`ollama run` pulls the model and opens a local chat. Quit after the first
successful reply. Confirm with:

```bash
ollama list
ollama ps
```

`ollama ps` shows whether the model is on GPU, CPU, or split.

### 9.2 Listen on the private network (optional)

Ollama binds `127.0.0.1:11434` by default. Same-machine setups can leave that
alone. Two-machine setups must bind all interfaces.

Set `OLLAMA_HOST=0.0.0.0:11434` using the official per-OS method
([Ollama FAQ](https://docs.ollama.com/faq)):

| OS | How |
| --- | --- |
| Windows | Quit Ollama from the tray. Settings → environment variables for your account → `OLLAMA_HOST` = `0.0.0.0:11434`. Restart Ollama from the Start menu. |
| Linux (systemd) | `sudo systemctl edit ollama.service` and add `Environment="OLLAMA_HOST=0.0.0.0:11434"` under `[Service]`. Then `daemon-reload` and restart. |
| macOS app | `launchctl setenv OLLAMA_HOST "0.0.0.0:11434"` and restart the app. |

Optional but useful:

```bash
OLLAMA_CONTEXT_LENGTH=16384
OLLAMA_KEEP_ALIVE=30m
```

Do **not** set a public-router port forward for 11434.

### 9.3 Firewall (LAN only)

Allow **inbound TCP 11434** on the **private / domain** profile only.

Windows (Administrator PowerShell), private profile:

```powershell
New-NetFirewallRule `
  -DisplayName "Ollama LAN" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 11434 `
  -Action Allow `
  -Profile Private
```

Linux example with ufw, restricted to a private subnet placeholder:

```bash
sudo ufw allow from 192.168.0.0/16 to any port 11434 proto tcp
```

### 9.4 Discover the inference-host address (local only)

Windows: `ipconfig` → IPv4 address.
Linux / macOS: `ip -4 addr` or `ifconfig`.

Record that address in the **workstation** environment as `OLLAMA_BASE_URL`.
Never commit it.

If the inference host is **Ubuntu in WSL2** on a second Windows PC, prefer
an SSH local forward and keep Ollama on WSL localhost. Public-safe commands
and placeholders: [examples/downstairs-wsl-gpu.md](examples/downstairs-wsl-gpu.md).

If the inference host is a **Halo-class AMD** box (future Phase 4), use the
same SSH-first pattern. Public-safe notes:
[examples/halo-ryzen-ai.md](examples/halo-ryzen-ai.md).

### 9.5 Sanity checks

On the inference host:

```bash
curl http://127.0.0.1:11434/api/tags
```

On the workstation (replace the placeholder; do not commit the real URL):

```bash
curl "$OLLAMA_BASE_URL/api/tags"
```

Chat smoke test:

```bash
curl "$OLLAMA_BASE_URL/api/chat" \
  -d '{
    "model": "qwen3.5:9b",
    "messages": [
      {"role": "user", "content": "Write a one-line health-check function in Python."}
    ],
    "stream": false,
    "options": {"num_ctx": 16384}
  }'
```

The GPU on the inference host does the work. The workstation only sends HTTP.

---

## 10. Client adapters

Committed configs live under `examples/` and use interpolation. Copy them to
the client path, or symlink after implementation exists. Keep real URLs in
`.env` / the user environment.

### 10.1 Cursor (premium + MCP)

**Premium side:** leave Cursor Ultra / included models unchanged. Do not set
Override OpenAI Base URL to Ollama.

**MCP side:** project file `.cursor/mcp.json` or user file `~/.cursor/mcp.json`.

Cursor stdio servers support `command`, `args`, `env`, and `envFile`. Values
may use `${env:NAME}`, `${workspaceFolder}`, and `${userHome}`.

Template: [`examples/cursor.mcp.json`](examples/cursor.mcp.json)

Project instructions (Cursor rules / user rules), public-safe:

```
When a coding task is mechanical (tests, boilerplate, local rename, summary),
call the local-coding-slm MCP tools instead of generating the full artifact
yourself. Prefer local_generate_tests, local_code, local_refactor,
local_explain, or local_review. Use model=fast first. Escalate to model=strong
only if the fast result is too weak. Review the tool output before applying it.
Do not send secrets, .env files, or credentials to those tools.
```

Cursor Agent uses MCP tools automatically when they are relevant. Users can
also ask for a tool by name.

**Cursor Cloud Agents** run on remote VMs and cannot reach a private LAN
Ollama host. This MCP server is for the local/desktop Cursor session.

### 10.2 GitHub Copilot (premium + MCP)

**IDE Agent (supported equivalent):**

- VS Code 1.99+ with Copilot Chat in Agent mode.
- Workspace config: `.vscode/mcp.json` (`servers` key, not `mcpServers`).
- User config: VS Code user `mcp.json`.
- Org Copilot Business/Enterprise: the "MCP servers in Copilot" policy must
  allow MCP.

Template: [`examples/vscode.mcp.json`](examples/vscode.mcp.json)

The example uses a VS Code `inputs` prompt for `OLLAMA_BASE_URL` so a LAN
address is never committed.

Visual Studio, JetBrains, Xcode, and Eclipse also support MCP with similar
stdio/HTTP shapes. Prefer VS Code Agent for the first integration.

**Copilot CLI** can load `~/.copilot/mcp-config.json` with a `mcpServers`
block. Same stdio command, env from the user shell.

**Copilot cloud agent / code review (not supported for this server):**

Those run on GitHub-hosted runners. A private Ollama URL is unreachable. Do
not add `local-coding-slm` to the repository Settings → Copilot → MCP servers
page.

### 10.3 Claude Code (premium + MCP)

**Local CLI (supported equivalent):**

- Project scope: `.mcp.json` at the repo root (safe to commit if it only uses
  `${OLLAMA_BASE_URL}` and defaults).
- User / local scope: `~/.claude.json` for machine-specific overrides.

Claude Code expands `${VAR}` and `${VAR:-default}` in `command`, `args`,
`env`, `url`, and `headers`.

Template: [`examples/claude.mcp.json`](examples/claude.mcp.json)

```bash
# optional: add from the CLI instead of copying the file
claude mcp add --scope project --transport stdio local-coding-slm \
  --env OLLAMA_BASE_URL -- \
  python "${CLAUDE_PROJECT_DIR:-.}/src/local_coding_slm/server.py"
```

Claude Code prompts once before enabling project-scoped servers from
`.mcp.json`. Reset with `claude mcp reset-project-choices` if needed.

Put the same routing paragraph from §10.1 in `CLAUDE.md` or a project skill.

**Claude Code cloud / remote sessions** cannot reach a private LAN host. Use a
local session on the workstation.

---

## 11. Compatibility matrix

| Capability | Cursor desktop | Copilot IDE Agent | Claude Code local | Cursor Cloud Agent | Copilot cloud agent |
| --- | --- | --- | --- | --- | --- |
| Premium model as orchestrator | Yes | Yes | Yes | Yes | Yes |
| Local stdio MCP on workstation | Yes | Yes | Yes | No | No |
| Reach private LAN Ollama | Yes, via local MCP | Yes, via local MCP | Yes, via local MCP | No | No |
| Project-shared public config | `.cursor/mcp.json` + env interpolation | `.vscode/mcp.json` + `inputs` | `.mcp.json` + `${VAR}` | n/a | n/a |
| Treat Ollama as a first-class model in the picker | Not for private LAN | Separate Copilot+Ollama flows; not this spec | Can use Ollama directly, but this spec uses MCP | No | No |
| OpenRouter required | No | No | No | No | No |

---

## 12. Security

### 12.1 Deployment

- Prefer Ollama on **`127.0.0.1`**. Reach a second GPU host with
  `ssh -L 11434:127.0.0.1:11434` (see `examples/downstairs-wsl-gpu.md`).
  Do **not** bind `0.0.0.0` unless you have a written reason.
- **No public port forward.** No ngrok, Cloudflare Tunnel, or similar.
- Do not send secrets, private keys, `.env` files, or credentials into MCP tool
  arguments.
- Committed configs must not contain IPs, hostnames, tokens, or usernames.
- The MCP server is a local process. It should talk only to `OLLAMA_BASE_URL`.
- If you later add any HTTP MCP transport, put it on localhost and authenticate
  it. Phase 1 stays on stdio.
- Treat MCP tool results as **untrusted model output**. The premium agent
  reviews before applying patches. A local model can still emit insecure or
  malicious code.

Run the defensive checker on the workstation after install or `.env` changes:

```bash
PYTHONPATH=src python3 scripts/check_deployment_safety.py
```

The checker looks at *this* host only: `OLLAMA_BASE_URL`, model tags, whether
`.env` is ignored, placeholder IPs in git, and whether port 11434 is listening
on a wildcard. It does **not** scan other machines and it cannot prove weights
are clean.

### 12.2 Open-weight models

Open weights are a **privacy** win (inference stays on your GPU). They are not
an alignment or integrity win.

- **Qwen is a family, not an SLM.** Large Qwen models are LLMs. The starter
  tag `qwen3.5:9b` is the SLM this repo means: ~9B, local, bounded generation.
- Official [Ollama library](https://ollama.com/library) tags only
  (`qwen3.5:9b`, `devstral-small-2`). Do not load a random GGUF, a stranger's
  fine-tune, or a `user/name` blob just because it "codes better."
- It is easy to ship a **trojaned SLM**: poisoned fine-tunes and unofficial
  weight files can look helpful and still plant backdoors in generated code.
  This repo will not document how to do that. Pull from the official library,
  pin the tags in `.env`, and review every patch.
- The checker can reject path/URL-shaped tags and public binds. It **cannot**
  detect a backdoor inside an otherwise normal-looking official tag. Review
  remains mandatory.
- Do not give the SLM shell, credentials, or unattended merge rights.

### 12.3 What local does not mean

The premium agent still sees the repo and the tool results. Local inference
is not an air gap. Keep household SSH facts and secrets out of MCP arguments
and out of git.

---

## 13. Public-repo hygiene

Allowed in git:

- This spec, README, example configs with placeholders.
- MCP server source.
- `.env.example` with dummy values.

Never commit:

- `.env`, `*.local.json`, real `OLLAMA_BASE_URL` values.
- Screenshots or logs that show a LAN IP, username, or home hostname.
- Firewall rules that encode a personal subnet unless written as examples.

Use placeholders in docs:

```
http://<inference-host>:11434
OLLAMA_BASE_URL
192.168.0.0/16          # example private range, not a real home net
```

---

## 14. Target repository layout

```
.
├── README.md
├── spec.md                          ← this document
├── .gitignore
├── .env.example
├── examples/
│   ├── cursor.mcp.json
│   ├── vscode.mcp.json
│   ├── claude.mcp.json
│   ├── downstairs-wsl-gpu.md        ← WSL GPU host via SSH (placeholders)
│   └── halo-ryzen-ai.md             ← future Halo-class AMD host (placeholders)
├── src/
│   └── local_coding_slm/
│       ├── server.py                ← stdio MCP server
│       ├── ollama_client.py
│       ├── envfile.py
│       └── prompts.py
├── docs/
│   ├── roadmap.md                   ← current vs future phases
│   ├── c4.md                        ← C4 context / container / component
│   └── phase3-log.md
├── scripts/
│   ├── run_mcp.sh                   ← project MCP entry (loads .env)
│   ├── prove_acceptance.py
│   └── check_deployment_safety.py   ← defensive bind / tag / git checks
└── tests/
    ├── test_ollama_client.py
    ├── test_envfile.py
    └── test_safety.py
```

Phase 1 of this repository is the spec, public-safe examples, and a running
local inference host. Phase 2 is the stdio MCP server in `src/local_coding_slm`.

---

## 15. Phased rollout

### Phase 1 — inference host only (do this first)

1. Install Ollama on the GPU machine (keep the current OS; no dual-boot).
2. Pull the fast model; confirm GPU placement with `ollama ps`.
3. Optionally expose LAN + firewall.
4. `curl` `/api/tags` and `/api/chat` from the workstation.
5. Pull the strong model and repeat one prompt.
6. **Stop.** Do not build routing until the fast model feels usable.

### Phase 2 — MCP bridge

1. Implement `src/local_coding_slm` as a stdio MCP server.
2. Wire Cursor with `examples/cursor.mcp.json`.
3. Run the acceptance tests in §16.
4. Copy the same server into Copilot and Claude Code configs.

### Phase 3 — measure, then maybe automate

Track, even informally:

- Local tool success rate (accepted vs rewritten by the premium model)
- Latency (fast vs strong)
- Escalation rate to the premium model
- Rough premium-token savings

Dated baseline evidence:
[docs/local-acceptance-results-2026-09-06.md](docs/local-acceptance-results-2026-09-06.md).
It distinguishes mocked unit tests from live Ollama/MCP checks and states the
limits of the current single-file refactor case.

Only after that, consider automatic task classification.

### Phase 4 — Halo-class AMD host (future)

Claim this only after Phase 3 has some numbers and the existing second
NVIDIA/WSL host is in a known state (on, or explicitly abandoned).

1. Treat Halo as another private Ollama host, not a second MCP product.
2. Keep `local_*` tool names and `OLLAMA_*` variables.
3. Prefer `ssh -L` to Halo localhost. Optional: private-interface bind
   plus a workstation-only firewall. No public tunnels.
4. Re-run A1–A7 and A11–A12 from the workstation. Run A4 (external
   reachability must fail).
5. After the starter pair is usable, benchmark larger official tags on
   Halo unified memory. Record tok/s, time to first token, and peak
   memory in a private note — not in git if the note identifies the
   machine.

Planning index: [docs/roadmap.md](docs/roadmap.md).

---

## 16. Acceptance tests

Run from the workstation with `OLLAMA_BASE_URL` set.

| ID | Check | Pass |
| --- | --- | --- |
| A1 | `curl $OLLAMA_BASE_URL/api/tags` | JSON lists `qwen3.5:9b` and `devstral-small-2` (or the configured tags) |
| A2 | Chat prompt to the fast model | Response in a few seconds; `ollama ps` shows GPU |
| A3 | Chat prompt to the strong model | Completes; GPU or GPU+RAM is acceptable |
| A4 | From a second machine, `curl` fails if firewall/bind is wrong | Documents LAN exposure; skip if same-machine |
| A5 | `local_status` MCP tool | Reports both models and the configured base URL host *without* requiring that URL in git |
| A6 | `local_generate_tests` with one small function | Returns a test file / diff the premium agent can apply |
| A7 | Cursor Agent | Premium model calls a `local_*` tool on a mechanical prompt |
| A8 | Copilot Agent (VS Code) | Same tool appears and runs |
| A9 | Claude Code local | `claude mcp list` shows `local-coding-slm` connected |
| A10 | Cloud agents | Documented as unsupported; no private URL in repo Copilot MCP settings |
| A11 | `git grep` for private IPs / usernames | No RFC1918 addresses except documented placeholders; no `@` emails |
| A12 | `scripts/check_deployment_safety.py` | Loopback (or SSH-forward) URL, official tags, `.env` ignored, no wildcard listen |
| A13 | Halo ROCm + `ollama ps` (Phase 4) | Accelerated placement on the Halo host; skip until that lab is claimed |

---

## 17. Out of scope

- OpenRouter or any extra paid router.
- Publishing Ollama through ngrok / Cloudflare Tunnel so Cursor can use it as
  a model provider.
- Dual-booting the inference host to Linux.
- Buying more system RAM solely to run larger SLMs (VRAM upgrade is the
  lever if 16 GB becomes the bottleneck).
- Automatic multi-model classifiers (phase 3).
- Cloud-agent access to the private GPU.

---

## 18. References

- [Ollama FAQ — host, env vars, context, GPU placement](https://docs.ollama.com/faq)
- [Ollama Windows download](https://ollama.com/download)
- [qwen3.5:9b](https://ollama.com/library/qwen3.5:9b)
- [devstral-small-2](https://ollama.com/library/devstral-small-2)
- [Cursor MCP](https://cursor.com/docs/mcp)
- [GitHub Copilot — MCP in the IDE](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/extend-copilot-chat-with-mcp)
- [GitHub Copilot — repository / cloud-agent MCP](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
