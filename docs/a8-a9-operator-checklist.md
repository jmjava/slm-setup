# T12 Part B — Copilot A8 / Claude A9 operator checklist

Public-safe steps for the **same-machine** workstation lab. This does **not**
touch the downstairs WSL host, Halo, or any public / LAN bind.

A8 and A9 are **operator-verified**. Config in git is not a pass. Do not record
a pass unless the named client actually listed the tools and ran one.

Official Ollama library tags only. Do not persist or paste secrets, `.env`
contents, or a private URL into git, chat logs, or screenshots.

## Current acceptance (same-machine lab)

Sources: [local acceptance 2026-09-06](local-acceptance-results-2026-09-06.md),
[security scan 2026-09-06](security-scan-results-2026-09-06.md),
[spec §16](../spec.md#16-acceptance-tests).

| ID | Status | Evidence |
| --- | --- | --- |
| A1 | Pass | Tags list includes `qwen3.5:9b` and `devstral-small-2` |
| A2 | Pass | Fast-model chat; GPU placement observed |
| A3 | Pass | Strong-model chat completed (split GPU/RAM acceptable) |
| A4 | Skip here | Same-machine profile. Two-machine SSH is T12 Part A (blocked) |
| A5 | Pass | `local_status` via stdio MCP reached real Ollama |
| A6 | Pass | `local_generate_tests` live acceptance |
| A7 | Pass | Cursor Agent called `local_*` on a mechanical prompt |
| **A8** | **Pending operator** | Copilot Agent in VS Code must list and **run** a `local_*` tool |
| **A9** | **Pending operator** | Local `claude mcp list` must show `local-coding-slm` **connected** |
| A10 | Pass (design) | No private URL in committed MCP JSON; do not add this server to repo Copilot cloud MCP settings |
| A11 | Pass | Dated secret / placeholder-IP scan |
| A12 | Pass | `scripts/check_deployment_safety.py` on loopback |
| A13 | Skip | Halo Phase 4 is not claimed |

## Before either client

1. Stay on this workstation. Do not change downstairs power, SSH, or Ollama bind.
2. Confirm the gitignored `.env` points at a **loopback** `OLLAMA_BASE_URL`
   (default example `http://127.0.0.1:11434`). If this lab uses a second
   user-local listener, type that loopback URL only in the client prompt or
   shell — never commit it.
3. Confirm `.venv` exists (`python3 -m venv .venv && .venv/bin/pip install -e .`).
4. Optional smoke (not a substitute for A8/A9):

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/prove_acceptance.py
   PYTHONPATH=src .venv/bin/python scripts/check_deployment_safety.py
   ```

Project files already committed:

- Copilot IDE: [`.vscode/mcp.json`](../.vscode/mcp.json) (template
  [`examples/vscode.mcp.json`](../examples/vscode.mcp.json))
- Copilot CLI (optional): copy
  [`examples/copilot-cli.mcp.json`](../examples/copilot-cli.mcp.json) to
  `~/.copilot/mcp-config.json` and replace the clone-path placeholder
- Claude Code: [`.mcp.json`](../.mcp.json) (template
  [`examples/claude.mcp.json`](../examples/claude.mcp.json))
- Claude routing: [`CLAUDE.md`](../CLAUDE.md)

Open PR **#12** (if still open) switches those JSON files to
`scripts/run_mcp.sh` so `.env` loads without a URL prompt. Either shape is
valid for this checklist. Do not add a LAN bind to make the prompt easier.

---

## A8 — Copilot Agent (VS Code)

Pass rule from spec §16: the same `local_*` tool **appears and runs**.

### Clicks and prompts

1. Open **this repository** in **VS Code 1.99+** (not Cursor, not Visual Studio).
2. Sign in to **GitHub Copilot Chat**. If the seat is Copilot Business /
   Enterprise, an admin must allow the **MCP servers in Copilot** policy.
3. Open `.vscode/mcp.json`. Use the CodeLens **Start** control on
   `local-coding-slm` (or Command Palette → `MCP: List Servers` → start it).
4. If VS Code prompts for **Ollama base URL**, keep the default
   `http://127.0.0.1:11434` **or** type the loopback URL from your `.env`.
   Do not type a LAN hostname. Do not screenshot the dialog if it shows a
   non-default URL.
5. Trust / allow the local stdio server if VS Code asks.
6. Command Palette → `MCP: List Servers`. Confirm `local-coding-slm` is
   running (not failed).
7. Open **Copilot Chat** (title-bar Copilot icon).
8. Set the mode dropdown to **Agent** (Ask / Edit is not A8).
9. Click the **tools** icon in the chat panel. Enable the
   `local-coding-slm` tools (`local_status`, `local_generate_tests`,
   `local_code`, `local_refactor`, `local_explain`, `local_review`).
10. Send exactly this prompt (or equivalent mechanical wording):

    > Call `local_status`, then `local_generate_tests` for a one-function
    > Python `add(a, b)`. Use model=fast. Do not send `.env` or secrets.

11. When Copilot asks to run a tool, click **Continue** / allow. That click
    is required; the agent cannot complete A8 without it.
12. Review the tool output. Treat it as untrusted. Do not apply a patch you
    have not read.

### Pass / fail

- **Pass:** Copilot Agent invoked at least one `local_*` tool and returned
  its result (status JSON or generated tests).
- **Fail:** tools missing, server failed to start, Copilot answered without
  calling a tool, or you only used Copilot CLI / cloud agent.
- **Not A8:** GitHub.com Copilot cloud agent, repository
  Settings → Copilot → MCP servers, or any hosted runner.

Record the date and “pass” or “fail” in a **private** note. Do not invent a
pass in this repo.

---

## A9 — Claude Code local

Pass rule from spec §16: `claude mcp list` shows `local-coding-slm`
**connected**.

### Clicks and commands

1. Use **local** Claude Code on this workstation. Do not use an
   Anthropic-hosted Claude Code cloud session.
2. From the repository root, start Claude Code (`claude`). On first use of
   this project it prompts to enable **project-scoped** MCP servers from
   `.mcp.json`. Choose **enable** for `local-coding-slm`.
3. If you previously denied that prompt, run
   `claude mcp reset-project-choices`, start Claude again, and enable it.
4. If this lab’s Ollama is not on `127.0.0.1:11434`, export
   `OLLAMA_BASE_URL` in the **same shell** that launches `claude` (loopback
   only). The committed `.mcp.json` defaults to `http://127.0.0.1:11434`
   when the variable is unset.
5. Run:

   ```bash
   claude mcp list
   ```

6. Optional second check, still local: in the Claude Code session ask it to
   call `local_status`. Approve the tool prompt once.

Optional instead of relying on the committed file:

```bash
claude mcp add --scope project --transport stdio local-coding-slm \
  --env OLLAMA_BASE_URL -- \
  python "${CLAUDE_PROJECT_DIR:-.}/src/local_coding_slm/server.py"
```

### Pass / fail

- **Pass:** `claude mcp list` prints `local-coding-slm` as **connected**
  (not merely configured / failed).
- **Fail:** Claude Code is not installed, the enable prompt was skipped,
  the server failed (wrong URL / missing `.venv`), or you only checked a
  hosted Claude session.
- **Not A9:** Anthropic-hosted cloud Claude Code.

Record the date and “pass” or “fail” in a **private** note.

---

## Out of scope for this checklist

- Downstairs WSL GPU / SSH (T12 Part A)
- Halo Phase 4 / A13
- Binding Ollama to `0.0.0.0` or a LAN interface
- Adding `local-coding-slm` to GitHub repository Copilot MCP settings
- Unofficial GGUFs or fine-tunes
