# Example: GPU inference host in WSL (public-safe)

A common home-lab split is:

- **Workstation** — IDE + `local-coding-slm` MCP
- **Second PC** — Windows, Ubuntu in WSL2, NVIDIA GPU, Ollama

This file uses placeholders only. Put the real SSH name, port, and LAN
address in a gitignored `.env` or `*.local.md`. Never commit them.

## Why SSH instead of a LAN bind

Keep Ollama on **WSL localhost**. From the workstation, forward the API:

```bash
ssh -N -p <ssh-port> -L 11434:127.0.0.1:11434 user@<wsl-host>
```

Then on the workstation (gitignored `.env`):

```
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

`<wsl-host>` is a name or address you already use. Do not scan for it.
`<ssh-port>` is often not 22 when Windows already owns port 22 — use
whatever `ssh` you already use to reach that WSL.

Documentation stand-ins (not a real household):

```
ssh -N -p 2222 -L 11434:127.0.0.1:11434 user@wsl-gpu.example
```

`wsl-gpu.example` and `192.0.2.0/24` are examples. They are not this lab.

## On the WSL host (when it is on)

1. Install a current Ollama. Distro packages can be too old.
2. Pull the starter tags and confirm `ollama ps` after one short chat.
3. Leave Ollama on `127.0.0.1:11434` if you use the SSH forward above.
4. The PC may be powered off when unused. Treat "no route" as host down
   before changing addresses.

Do **not** port-forward 11434 or 22/2222 through a public router.

## What not to commit

- Real hostnames, Windows computer names, usernames, or RFC1918 addresses
- A working `OLLAMA_BASE_URL` that identifies the house
- Screenshots of `ssh` or `ip addr` from that machine
