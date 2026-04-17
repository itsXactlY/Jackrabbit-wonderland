# Hermes-Crypto Documentation

> Zero-knowledge AES256-GCM encryption layer for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

## Table of Contents

- [Architecture](architecture.md) — System design, data flow, component interaction
- [Components](components.md) — Deep-dive into each module
- [API Reference](api.md) — Every class, method, and CLI command
- [Deployment](deployment.md) — Installation, systemd services, firewall
- [Configuration](configuration.md) — All config options and environment variables
- [Security Model](security.md) — Threat model, attack surface, limitations
- [Integration](integration.md) — Hermes plugin, PULSE, Neural Memory, external systems
- [Gateway](gateway.md) — HTTP/TCP API, Web UI, device access
- [Troubleshooting](troubleshooting.md) — Common issues and solutions

## Quick Start

```bash
git clone https://github.com/itsXactlY/hermes-crypto.git
cd hermes-crypto
sudo bash install.sh

# Verify
systemctl status jackrabbit-dlm@$USER
systemctl status hermes-gateway@$USER

# Test from browser
http://192.168.0.2:8080
```

## What This Solves

LLM providers log everything. Your ਖੋਜ, your trades, your medical questions — all visible to provider employees, auditors, and data-mining pipelines.

hermes-crypto encrypts every query before it leaves your machine. Provider sees base64 blobs. Nobody reviews millions of base64 logs.

```
You: "¿Cuántos idiomas se hablan en Camerún?"
Wire: "remember:: SG93IGRvZXMgYSBDUFUgY2FjaGUgd29yaz8="
Provider: sees a "memory recall protocol" with base64 payload
```

## Requirements

- Python 3.8+
- `pycryptodome` (auto-installed)
- JackrabbitDLM (auto-cloned if missing)
- Linux with systemd + nftables
- sudo access (for services + firewall)
