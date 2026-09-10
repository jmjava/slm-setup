# Phase 3 measurement log

Informal track of local-coding-slm tool calls. Do not put hostnames, LAN
IPs, or secrets here.

Reproducible commands, complete 2026-09-06 observations, and limitations:
[local-acceptance-results-2026-09-06.md](local-acceptance-results-2026-09-06.md).
Scoring method: [evaluation-protocol.md](evaluation-protocol.md).
Cloud-safe stub + apply-gate run:
[cloud-orchestrator-results-2026-09-07.md](cloud-orchestrator-results-2026-09-07.md).

| Date | Tool | Model | Task | Result | Notes |
| --- | --- | --- | --- | --- | --- |
| 2026-09-04 | local_generate_tests | fast | unittest for `merge_dotenv` | accepted with trim | Dropped one truncated test; quoted-value case kept; applied as `tests/test_envfile.py` |
| 2026-09-06 | local_generate_tests | fast | live A6 tests for synthetic `add()` | accepted | Real Ollama via stdio MCP; **shape-only** A6 at that date |
| 2026-09-06 | local_refactor | fast | extract module-level whitespace helper | accepted | Real Ollama; generated module parsed and preserved behavior across 3 executed cases; warm run 6.7s |
| 2026-09-06 | local_refactor | strong | extract module-level whitespace helper | accepted | Real Ollama; generated module parsed and preserved behavior across 3 executed cases; warm run 25.6s; model reported 46% CPU / 54% GPU at 16K context |
| 2026-09-07 | all local_* eval tools | stub | 10-case corpus + apply gate | accepted / rewritten / rejected per job | Cloud Agent; no GPU; A6 now executes tests |
| 2026-09-10 | local_refactor | fixtures | harder multi-file suite (3 cases) | scorer only | Offline corpus + runner; no live rate; Halo not started |
| 2026-09-10 | local_refactor | fixtures | harder suite + `rename_kwarg_across_files` | scorer only | Fourth case; leftover `subject=` alias vs colon-join drift; no live rate |
| 2026-09-10 | local_refactor | fixtures | harder suite + `rename_payload_key_across_files` | scorer only | Fifth case; leftover `user_id` key / `.get()` alias vs `acct:` prefix drift; no live rate |
| 2026-09-10 | local_refactor | fixtures | harder suite + `rename_env_var_across_files` | scorer only | Sixth case; leftover `APP_TOKEN` getenv / `.get()` alias vs `tok:` prefix drift; no live rate |

Columns:

- **Result:** `accepted` / `accepted with trim` / `rewritten` / `escalated`
- **Task:** one-line, no private paths

The refactor acceptance initially said only "private helper." The strong model
reasonably produced a nested helper while the checker expected a module-level
helper. Tightening the task to "module-level (top-level) private helper" made
the requirement and assertion agree. Treat prompt precision as part of the
test contract, not as a model-quality afterthought.
