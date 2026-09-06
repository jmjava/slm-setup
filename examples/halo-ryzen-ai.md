# Example: Halo-class AMD inference host (future, public-safe)

A later home-lab split is:

- **Workstation** — IDE + `local-coding-slm` MCP (unchanged)
- **Halo-class AMD box** — Ryzen AI APU, unified memory, Ollama + ROCm

This file is a **future host profile**, not a current install guide.
It uses placeholders only. Put the real hostname, SSH name, and address
in a gitignored `.env` or `*.local.md`. Never commit them.

The MCP tool names and `OLLAMA_*` variables do not change. Only the
Ollama host changes. See [docs/roadmap.md](../docs/roadmap.md) Phase 4.

## Prefer SSH instead of a LAN bind

Keep Ollama on **Halo localhost**. From the workstation, forward the API:

```bash
ssh -N -L 11434:127.0.0.1:11434 user@<halo-host>
```

Then on the workstation (gitignored `.env`):

```
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

`<halo-host>` is a name you already use. Do not scan for it.

Documentation stand-ins (not a real household):

```
ssh -N -L 11434:127.0.0.1:11434 user@halo-private-host.example
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

The deployment checker warns on a private LAN URL and fails on a public
or tunnel URL. Re-run it after any `.env` change.

## On the Halo (when this phase is claimed)

1. Install a current Ollama with AMD ROCm. Distro packages can be too old.
2. Pull the starter tags (`qwen3.5:9b`, `devstral-small-2`) and confirm
   `ollama ps` after one short chat.
3. Leave Ollama on `127.0.0.1:11434` if you use the SSH forward above.
4. Treat "no route" as host down before changing addresses.

Do **not** port-forward 11434 through a public router. Do not add Halo
to Cursor's model picker. Cloud agents cannot reach this host.

## What not to commit

- Real hostnames, usernames, or RFC1918 addresses
- A working `OLLAMA_BASE_URL` that identifies the house
- Screenshots of `ssh`, `ip addr`, or ROCm device lists from that machine
- Halo serials or exact SKU purchase details
