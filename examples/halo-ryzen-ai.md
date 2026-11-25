# Example: Halo-class AMD inference host (current paper host, public-safe)

Home-lab split as of **25 Nov 2026**:

- **Workstation** — IDE + `local-coding-slm` MCP (unchanged)
- **Halo-class AMD box (GEEKOM)** — Ryzen AI APU, unified memory, primary
  private Ollama host for Phase 3 / paper live rows

This file is the **current** Halo host profile. It uses placeholders only.
Put the real hostname, SSH name, and address in a gitignored `.env` or
`*.local.md`. Never commit them.

The MCP tool names and `OLLAMA_*` variables do not change. Only the
Ollama host changes. See [docs/roadmap.md](../docs/roadmap.md) Phase 4
(active) and [docs/harness-host-plan.md](../docs/harness-host-plan.md).

## Prefer SSH instead of a LAN bind

Keep Ollama on **Halo localhost**. From the workstation, forward the API:

```bash
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:11436:127.0.0.1:11434 user@<halo-host>
```

Then on the workstation (gitignored `.env`):

```
OLLAMA_BASE_URL=http://127.0.0.1:11436
```

`11436` is an example unused port on the workstation. `11434` is Ollama's
loopback port on Halo. `<halo-host>` is a name you already use. Do not scan
for it. The harness-host plan may use `11440` for the same forward — pick one
and keep it consistent in `.env`.

Documentation stand-ins (not a real household):

```
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:11436:127.0.0.1:11434 user@halo-private-host.example
```

`halo-private-host.example` and `192.0.2.0/24` are examples. They are
not this lab.

## Optional private LAN bind

If SSH is not practical, bind Ollama to the Halo **private** interface
only and allow TCP `11434` from the workstation address. Do **not** use
`0.0.0.0` without a written reason. Do **not** port-forward 11434.

Workstation `.env` in that case (placeholder only):

```
# OLLAMA_BASE_URL=http://<halo-host>:11434
```

The workstation deployment checker warns on a private LAN URL and fails on a
public or tunnel URL. It can inspect only listeners on the workstation; verify
the remote Ollama bind separately on Halo. Re-run it after any `.env` change.

## On the Halo

1. Validate the current Ollama release on the Halo with its supported AMD
   backend. Record whether ROCm or Vulkan is used; do not assume either path
   before testing the actual machine.
2. Pull the starter tags (`qwen3.5:9b`, `devstral-small-2`) only after the
   runtime answers on loopback, then confirm accelerated placement after one
   short chat (acceptance A13).
3. Leave Ollama on `127.0.0.1:11434` if you use the SSH forward above.
4. Treat "no route" as host down before changing addresses.
5. Label live harness rows `host_class=halo-395`. Fall back to downstairs
   NVIDIA only if placement fails; do not use the IDE workstation for paper
   rates.

Do **not** port-forward 11434 through a public router. Do not add Halo to
Cursor's model picker. Default vendor-hosted cloud agents are not connected to
this home-lab host; private-connectivity or self-hosted enterprise
configurations are separate designs.

## What not to commit

- Real hostnames, usernames, or RFC1918 addresses
- A working `OLLAMA_BASE_URL` that identifies the house
- Screenshots of `ssh`, `ip addr`, or ROCm device lists from that machine
- Halo serials or exact SKU purchase details
