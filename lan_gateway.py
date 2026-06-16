#!/usr/bin/env python3
"""
Hermes Zero-Knowledge LAN Gateway
===================================
Tiny HTTP server for controlling Hermes from any device on the LAN.
Works from: browser, curl, netcat, iOS Shortcuts, any HTTP client.

Features:
  - Web UI (minimal, mobile-friendly)
  - JSON API (POST /command)
  - Netcat compatible (raw TCP on :37374)
  - remember:: protocol (base64) for provider transport
  - AES256-GCM for local storage only (Neural Memory, PULSE cache)
  - DLM vault key storage
  - Session management

Usage:
  python3 lan_gateway.py                  # Start on 0.0.0.0:8080
  python3 lan_gateway.py --port 9090      # Custom port
  python3 lan_gateway.py --no-crypto      # Disable encryption (debug)

Access:
  http://192.168.0.2:8080                 # Browser
  curl -X POST http://192.168.0.2:8080/command -d '{"cmd":"status"}'
  echo '{"cmd":"status"}' | nc 192.168.0.2 37374
"""

import http.server
import socketserver
import json
import os
import sys
import subprocess
import threading
import socket
import secrets
import re
import shlex
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from datetime import datetime

# Add hermes-crypto to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from crypto_middleware import CryptoMiddleware
from remember_protocol import RememberProtocol


# ================================================================
# CONFIG
# ================================================================

def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_csv(name: str, default: str) -> set:
    value = os.environ.get(name, default)
    return {part.strip().lower() for part in value.split(",") if part.strip()}


GATEWAY_PORT = _env_int("GATEWAY_PORT", 8080)
RAW_TCP_PORT = _env_int("RAW_TCP_PORT", 37374)
DLM_HOST = os.environ.get("DLM_HOST", "127.0.0.1").strip() or "127.0.0.1"
DLM_PORT = _env_int("DLM_PORT", 37373)
SESSION_TTL = _env_int("SESSION_TTL", 3000)  # DLM-safe default
HERMES_BIN = os.environ.get("HERMES_BIN", "hermes").strip() or "hermes"

# --- LAN hardening: bearer-token auth + TLS + client-key delivery ---------
# The gateway exposes shell/hermes/pulse over /command. Unauthenticated that is
# remote code execution for anything on the WLAN. When a token is provisioned
# (GATEWAY_TOKEN env or token file), protected commands require it. With no
# token configured, auth is OFF (legacy/dev/localhost behaviour preserved).
_HC_HOME = os.path.expanduser(os.environ.get("HERMES_CRYPTO_HOME", "~/.hermes-crypto"))
GATEWAY_TOKEN_FILE = os.path.expanduser(
    os.environ.get("GATEWAY_TOKEN_FILE", os.path.join(_HC_HOME, "gateway.token"))
)


def _load_gateway_token() -> str:
    tok = os.environ.get("GATEWAY_TOKEN", "").strip()
    if tok:
        return tok
    try:
        with open(GATEWAY_TOKEN_FILE) as fh:
            return fh.read().strip()
    except OSError:
        return ""


GATEWAY_TOKEN = _load_gateway_token()
# Commands that perform code execution, data egress, or touch crypto state and
# must never run unauthenticated once a token is configured. status / chaff /
# health stay open for liveness checks and the Web UI.
PROTECTED_COMMANDS = _env_csv(
    "GATEWAY_PROTECTED_COMMANDS",
    "shell,hermes,pulse,encrypt,decrypt,key,roundtrip,session,kill",
)
GATEWAY_TLS_CERT = os.path.expanduser(
    os.environ.get("GATEWAY_TLS_CERT", os.path.join(_HC_HOME, "gateway.crt"))
)
GATEWAY_TLS_KEY = os.path.expanduser(
    os.environ.get("GATEWAY_TLS_KEY", os.path.join(_HC_HOME, "gateway.key"))
)
PULSE_SCRIPT = os.path.expanduser(
    os.environ.get("PULSE_SCRIPT", "~/projects/pulse/scripts/pulse.py")
)
UPSTREAM_PROVIDER = (
    os.environ.get("WONDERLAND_UPSTREAM_PROVIDER")
    or os.environ.get("HERMES_INFERENCE_PROVIDER")
    or "openrouter"
).strip().lower()
UPSTREAM_BASE_URL = (
    os.environ.get("WONDERLAND_UPSTREAM_BASE_URL")
    or os.environ.get("UPSTREAM_BASE_URL")
    or ""
).strip().rstrip("/")
UPSTREAM_MODEL = (
    os.environ.get("WONDERLAND_UPSTREAM_MODEL")
    or os.environ.get("HERMES_UPSTREAM_MODEL")
    or os.environ.get("LLM_MODEL")
    or ""
).strip()
UPSTREAM_API_KEY = (
    os.environ.get("WONDERLAND_UPSTREAM_API_KEY")
    or os.environ.get("UPSTREAM_API_KEY")
    or ""
).strip()

# Manual override / fallback when the upstream /models endpoint omits or
# under-reports context_length.  MiniMax-M2 (~204800), Kimi-K2 (~131072),
# GLM-4.6 (~200000), etc.  Set in gateway.env.
UPSTREAM_CONTEXT_LENGTH = _env_int("WONDERLAND_UPSTREAM_CONTEXT_LENGTH", 0)
UPSTREAM_MAX_OUTPUT_TOKENS = _env_int("WONDERLAND_UPSTREAM_MAX_OUTPUT_TOKENS", 0)

# Model names that mean "use this gateway/proxy", not a real upstream model.
# Without this, `hermes chat -m wonderland` sends model="wonderland" to the
# configured provider and fails with "unknown/unsupported model".  The proxy
# alias is resolved at execution time to the normal Hermes model/provider/API key.
PROXY_MODEL_ALIASES = _env_csv("PROXY_MODEL_ALIASES", "wonderland,hermes-agent,proxy,default")

# Provider flags accepted by `hermes chat --provider ...`.
CLI_PROVIDER_CHOICES = {
    "auto", "openrouter", "nous", "openai-codex", "copilot-acp", "copilot",
    "anthropic", "gemini", "huggingface", "zai", "kimi-coding", "minimax",
    "minimax-cn", "kilocode", "xiaomi",
}

PROVIDER_ENV_KEYS = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "nous": ("NOUS_API_KEY",),
    "openai-codex": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN"),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "huggingface": ("HF_TOKEN",),
    "zai": ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
    "kimi-coding": ("KIMI_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
    "minimax-cn": ("MINIMAX_CN_API_KEY",),
    "kilocode": ("KILOCODE_API_KEY",),
    "xiaomi": ("XIAOMI_API_KEY",),
}

PROVIDER_BASE_URL_ENV_KEYS = {
    "openrouter": "OPENROUTER_BASE_URL",
    "openai-codex": "OPENAI_BASE_URL",
    "anthropic": "ANTHROPIC_BASE_URL",
    "gemini": "GEMINI_BASE_URL",
    "zai": "GLM_BASE_URL",
    "kimi-coding": "KIMI_BASE_URL",
    "minimax": "MINIMAX_BASE_URL",
    "minimax-cn": "MINIMAX_CN_BASE_URL",
    "kilocode": "KILOCODE_BASE_URL",
    "xiaomi": "XIAOMI_BASE_URL",
}

UPSTREAM_PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "huggingface": "https://router.huggingface.co/v1",
    "zai": "https://api.z.ai/api/paas/v4",
    "kimi-coding": "https://api.moonshot.ai/v1",
    "minimax": "https://api.minimax.io/v1",
    "minimax-cn": "https://api.minimaxi.com/v1",
    "kilocode": "https://api.kilo.ai/api/gateway",
    "xiaomi": "https://api.xiaomi.com/v1",
}

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def hermes_command() -> list:
    """Return the configured Hermes command as argv-safe parts."""
    try:
        return shlex.split(HERMES_BIN) or ["hermes"]
    except ValueError:
        return [HERMES_BIN]


def _parse_env_assignments(line: str):
    """Yield KEY=VALUE assignments from one .env line.

    Supports the usual one-assignment-per-line format and the broken-but-common
    `A=1 B=2` format. This matters here because the gateway is long-lived and
    must pass fresh provider keys to subprocesses.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return
    if line.startswith("export "):
        line = line[7:].strip()
    try:
        parts = shlex.split(line, comments=True, posix=True)
    except ValueError:
        parts = [line]
    if not parts:
        return
    for part in parts:
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            yield key, value.strip()


def build_hermes_env() -> dict:
    """Inherit process env and overlay ~/.hermes/.env without leaking secrets."""
    env = os.environ.copy()
    hermes_env = os.path.expanduser("~/.hermes/.env")
    if os.path.isfile(hermes_env):
        with open(hermes_env, encoding="utf-8", errors="replace") as f:
            for line in f:
                for key, value in _parse_env_assignments(line) or ():
                    env[key] = value
    return env


def _minimal_config_parse(text: str) -> dict:
    """Tiny YAML fallback for the keys this gateway needs."""
    cfg = {}
    current = None
    current_child = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and line.endswith(":"):
            current = line[:-1]
            cfg.setdefault(current, {})
            current_child = None
            continue
        if current == "model" and indent >= 2 and ":" in line:
            key, _, value = line.partition(":")
            cfg.setdefault("model", {})[key.strip()] = value.strip().strip("'\"")
        elif current == "providers" and indent == 2 and line.endswith(":"):
            current_child = line[:-1]
            cfg.setdefault("providers", {}).setdefault(current_child, {})
        elif current == "providers" and current_child and indent >= 4 and ":" in line:
            key, _, value = line.partition(":")
            cfg.setdefault("providers", {}).setdefault(current_child, {})[key.strip()] = value.strip().strip("'\"")
    return cfg


def load_hermes_config() -> dict:
    path = os.path.expanduser("~/.hermes/config.yaml")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return _minimal_config_parse(text)


def resolve_hermes_runtime(env: dict = None) -> dict:
    """Resolve the normal Hermes model/provider/base_url/api_key for proxy use."""
    env = env or build_hermes_env()
    cfg = load_hermes_config()
    model_cfg = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
    providers = cfg.get("providers") if isinstance(cfg.get("providers"), dict) else {}

    model = (
        str(model_cfg.get("default") or model_cfg.get("model") or model_cfg.get("default_model") or "").strip()
        or env.get("LLM_MODEL", "").strip()
    )
    provider = str(model_cfg.get("provider") or env.get("HERMES_INFERENCE_PROVIDER") or "auto").strip().lower()
    base_url = str(model_cfg.get("base_url") or "").strip().rstrip("/")
    api_key = str(model_cfg.get("api_key") or model_cfg.get("api") or "").strip()

    p_cfg = providers.get(provider) if isinstance(providers.get(provider), dict) else {}
    if p_cfg:
        model = model or str(p_cfg.get("default_model") or p_cfg.get("model") or "").strip()
        base_url = base_url or str(p_cfg.get("api") or p_cfg.get("base_url") or "").strip().rstrip("/")
        api_key = api_key or str(p_cfg.get("api_key") or "").strip()

    if not api_key:
        for key in PROVIDER_ENV_KEYS.get(provider, ()):  # keep provider-specific keys provider-specific
            value = env.get(key, "").strip()
            if value:
                api_key = value
                break

    # Make subprocess resolution deterministic when we have explicit config.
    if provider and provider != "auto":
        env["HERMES_INFERENCE_PROVIDER"] = provider
    if api_key:
        for key in PROVIDER_ENV_KEYS.get(provider, ()):
            env.setdefault(key, api_key)
    if base_url:
        base_key = PROVIDER_BASE_URL_ENV_KEYS.get(provider)
        if base_key:
            env.setdefault(base_key, base_url)

    return {
        "model": model,
        "provider": provider,
        "base_url": base_url,
        "api_key_present": bool(api_key),
    }


def resolve_wonderland_upstream(env: dict = None) -> dict:
    """Resolve the upstream OpenAI-compatible provider for Wonderland proxying."""
    env = env or os.environ.copy()
    provider = (
        env.get("WONDERLAND_UPSTREAM_PROVIDER")
        or env.get("HERMES_INFERENCE_PROVIDER")
        or UPSTREAM_PROVIDER
        or "openrouter"
    ).strip().lower()
    model = (
        env.get("WONDERLAND_UPSTREAM_MODEL")
        or env.get("HERMES_UPSTREAM_MODEL")
        or env.get("LLM_MODEL")
        or UPSTREAM_MODEL
    ).strip()
    base_url = (
        env.get("WONDERLAND_UPSTREAM_BASE_URL")
        or env.get("UPSTREAM_BASE_URL")
        or UPSTREAM_BASE_URL
        or UPSTREAM_PROVIDER_BASE_URLS.get(provider, "")
    ).strip().rstrip("/")
    api_key = (
        env.get("WONDERLAND_UPSTREAM_API_KEY")
        or env.get("UPSTREAM_API_KEY")
        or UPSTREAM_API_KEY
        or ""
    ).strip()
    if not api_key:
        for key in PROVIDER_ENV_KEYS.get(provider, ()):
            value = env.get(key, "").strip()
            if value:
                api_key = value
                break
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "api_key_present": bool(api_key),
    }


_UPSTREAM_MODELS_CACHE = {"key": None, "expires": 0.0, "data": []}
_UPSTREAM_MODELS_TTL = 300.0


def _fetch_upstream_models(upstream: dict) -> list:
    """Pull the upstream provider's /models list, cached for _UPSTREAM_MODELS_TTL.

    Returns a list of OpenAI-shaped model dicts (id, context_length, ...).
    Empty list on any failure — callers must tolerate that.
    """
    import time
    base = (upstream.get("base_url") or "").rstrip("/")
    api_key = upstream.get("api_key") or ""
    if not base or not api_key:
        return []
    cache_key = (base, api_key[:12])
    now = time.time()
    if _UPSTREAM_MODELS_CACHE["key"] == cache_key and now < _UPSTREAM_MODELS_CACHE["expires"]:
        return _UPSTREAM_MODELS_CACHE["data"]
    try:
        req = Request(base + "/models", headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "wonderland-gateway/1.0",
        })
        with urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, json.JSONDecodeError, OSError):
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    _UPSTREAM_MODELS_CACHE.update(key=cache_key, expires=now + _UPSTREAM_MODELS_TTL, data=data)
    return data


def _model_context_fields(entry: dict) -> dict:
    """Pull context_length / max output token fields out of an upstream model entry.

    Different providers spell these differently — OpenRouter uses
    `context_length`, some use `max_context_length` or nest under
    `top_provider`.  Keep it permissive.
    """
    out = {}
    if not isinstance(entry, dict):
        return out
    top = entry.get("top_provider") if isinstance(entry.get("top_provider"), dict) else {}
    ctx = (
        entry.get("context_length")
        or entry.get("max_context_length")
        or entry.get("context_window")
        or top.get("context_length")
    )
    if isinstance(ctx, int) and ctx > 0:
        out["context_length"] = ctx
    max_out = (
        entry.get("max_completion_tokens")
        or entry.get("max_output_tokens")
        or top.get("max_completion_tokens")
    )
    if isinstance(max_out, int) and max_out > 0:
        out["max_completion_tokens"] = max_out
    return out


_MODELS_DEV_CACHE = {"expires": 0.0, "data": None}
_MODELS_DEV_TTL = 3600.0
_MODELS_DEV_URL = "https://models.dev/api.json"


def _fetch_models_dev() -> dict:
    """Pull the models.dev catalogue, cached for an hour.

    models.dev is the same registry hermes-agent consults — using it here means
    direct providers (MiniMax, Z.AI, Kimi, etc.) that omit `context_length`
    on `/v1/models` still get a real value advertised downstream.
    """
    import time
    now = time.time()
    if _MODELS_DEV_CACHE["data"] is not None and now < _MODELS_DEV_CACHE["expires"]:
        return _MODELS_DEV_CACHE["data"]
    try:
        req = Request(_MODELS_DEV_URL, headers={"User-Agent": "wonderland-gateway/1.0"})
        with urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, json.JSONDecodeError, OSError):
        return _MODELS_DEV_CACHE["data"] or {}
    if not isinstance(payload, dict):
        return {}
    _MODELS_DEV_CACHE.update(expires=now + _MODELS_DEV_TTL, data=payload)
    return payload


def _models_dev_lookup(provider: str, model: str) -> dict:
    """Find context/output limits for provider+model in the models.dev catalogue."""
    if not provider or not model:
        return {}
    catalogue = _fetch_models_dev()
    # models.dev keys vary in casing — try a few common spellings before giving up.
    p = provider.lower()
    candidates = [provider, p, p.replace("-", ""), p.replace("_", "-")]
    if p == "minimax-cn":
        candidates.append("minimax")  # same model catalogue
    pdata = None
    for key in candidates:
        if key in catalogue and isinstance(catalogue[key], dict):
            pdata = catalogue[key]
            break
    if not pdata:
        return {}
    models = pdata.get("models", {})
    entry = models.get(model) if isinstance(models, dict) else None
    if not isinstance(entry, dict):
        return {}
    out = {}
    limit = entry.get("limit") if isinstance(entry.get("limit"), dict) else entry
    ctx = limit.get("context")
    if isinstance(ctx, int) and ctx > 0:
        out["context_length"] = ctx
    max_out = limit.get("output")
    if isinstance(max_out, int) and max_out > 0:
        out["max_completion_tokens"] = max_out
    return out


def resolve_upstream_model_meta(upstream: dict) -> dict:
    """Find context_length etc. for the configured upstream model.

    Order: env var override > upstream /v1/models entry > models.dev catalogue.
    First two are exact; models.dev is a community registry and may lag, but
    direct providers (MiniMax, Kimi, Z.AI, ...) often omit context_length on
    their /models endpoint, and falling back here beats Hermes' default 128K.
    """
    meta = {}
    upstream_id = (upstream.get("model") or "").strip()
    if upstream_id:
        for entry in _fetch_upstream_models(upstream):
            if str(entry.get("id") or "").strip() == upstream_id:
                meta.update(_model_context_fields(entry))
                break
    if "context_length" not in meta and upstream_id:
        meta.update({k: v for k, v in _models_dev_lookup(upstream.get("provider", ""), upstream_id).items() if k not in meta})
    if UPSTREAM_CONTEXT_LENGTH > 0:
        meta["context_length"] = UPSTREAM_CONTEXT_LENGTH
    if UPSTREAM_MAX_OUTPUT_TOKENS > 0:
        meta["max_completion_tokens"] = UPSTREAM_MAX_OUTPUT_TOKENS
    return meta


def _session_for_openai_request(headers, data: dict) -> dict:
    session_id = headers.get("X-Hermes-Session-Id") or headers.get("X-Wonderland-Session-Id")
    if isinstance(data.get("metadata"), dict):
        session_id = session_id or data["metadata"].get("session_id")
    session = sessions.get_session(session_id)
    if session:
        return session
    created = sessions.create_session()
    return sessions.get_session(created["session_id"])


AES_UPSTREAM_BLOCKLIST = (
    "AES",
    "ENC_MSG:",
    "SESSION_CRYPTO",
    "SESSION KEY",
    "KEY:",
    "private key",
    "public key",
    "-----BEGIN",
    "-----END",
)


def _remember_protocol(session: dict) -> RememberProtocol:
    rp = session.get("remember")
    if not isinstance(rp, RememberProtocol):
        rp = RememberProtocol()
        session["remember"] = rp
        session["remember_header"] = rp.system_prompt_header()
    return rp


def _strip_forbidden_upstream_material(text: str) -> str:
    """Never forward AES protocol/key material to real LLM endpoints."""
    if not isinstance(text, str):
        return text
    safe_lines = []
    for line in text.splitlines():
        upper = line.upper()
        if any(marker.upper() in upper for marker in AES_UPSTREAM_BLOCKLIST):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def _remember_text_for_provider(session: dict, text: str) -> str:
    """Encode `text` for upstream LLM transport using Remember Protocol.

    Idempotent: if `text` is already a `remember::` payload (e.g. from a
    Hermes-side plugin that pre-encoded the message), pass it through after
    AES-marker stripping. Re-encoding would yield `remember::<base64-of-
    remember::...>` which the LLM can only single-decode, breaking the flow.
    """
    safe = _strip_forbidden_upstream_material(text)
    if safe.lstrip().startswith("remember::"):
        return safe
    return _remember_protocol(session).encode(safe)


def _remember_openai_content(session: dict, content):
    if isinstance(content, str):
        return _remember_text_for_provider(session, content)
    if isinstance(content, list):
        remembered = []
        for item in content:
            if not isinstance(item, dict):
                remembered.append(item)
                continue
            copied = dict(item)
            if isinstance(copied.get("text"), str):
                copied["text"] = _remember_text_for_provider(session, copied["text"])
            elif isinstance(copied.get("content"), str):
                copied["content"] = _remember_text_for_provider(session, copied["content"])
            remembered.append(copied)
        return remembered
    return content


def remember_openai_messages(session: dict, messages: list) -> list:
    """Encode upstream LLM payloads with Remember Protocol only."""
    rp = _remember_protocol(session)
    remembered = [
        {
            "role": "system",
            "content": session.get("remember_header") or rp.system_prompt_header(),
        }
    ]
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        copied = dict(msg)
        role = str(copied.get("role") or "").lower()
        if role in {"user", "tool"}:
            copied["content"] = _remember_openai_content(session, copied.get("content", ""))
        elif isinstance(copied.get("content"), str):
            copied["content"] = _strip_forbidden_upstream_material(copied["content"])
        remembered.append(copied)
    return remembered


def decode_openai_response(session: dict, response: dict) -> dict:
    """Best-effort Remember Protocol response decoding for non-streaming completions."""
    try:
        choices = response.get("choices") or []
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            message["content"] = _remember_protocol(session).decode_response(content)
    except Exception:
        pass
    return response


def _has_flag(argv: list, *flags: str) -> bool:
    return any(part in flags or any(part.startswith(f + "=") for f in flags if f.startswith("--")) for part in argv)


def prepare_hermes_argv(args: str, env: dict = None) -> tuple[list, dict]:
    """Parse user args and rewrite proxy model aliases to the real runtime model."""
    env = env or build_hermes_env()
    argv = shlex.split(args)
    if not argv:
        return argv, resolve_hermes_runtime(env)

    runtime = resolve_hermes_runtime(env)
    if argv[0] != "chat":
        return argv, runtime

    def _replace_model_at(index: int, value_index: int):
        requested = argv[value_index].strip().lower()
        if requested in PROXY_MODEL_ALIASES:
            model = runtime.get("model") or ""
            if model:
                argv[value_index] = model
            else:
                # No runtime model found: drop the explicit proxy alias so Hermes
                # can fall back to its own config instead of sending "wonderland".
                del argv[index:value_index + 1]
            provider = runtime.get("provider") or ""
            if provider in CLI_PROVIDER_CHOICES and not _has_flag(argv, "--provider"):
                argv.extend(["--provider", provider])
            return True
        return False

    i = 1
    while i < len(argv):
        part = argv[i]
        if part in ("-m", "--model") and i + 1 < len(argv):
            _replace_model_at(i, i + 1)
            break
        if part.startswith("--model="):
            requested = part.split("=", 1)[1].strip().lower()
            if requested in PROXY_MODEL_ALIASES:
                model = runtime.get("model") or ""
                if model:
                    argv[i] = f"--model={model}"
                else:
                    del argv[i]
                provider = runtime.get("provider") or ""
                if provider in CLI_PROVIDER_CHOICES and not _has_flag(argv, "--provider"):
                    argv.extend(["--provider", provider])
            break
        i += 1
    return argv, runtime


def openai_messages_to_prompt(messages: list) -> str:
    """Flatten OpenAI chat messages into a single Hermes CLI query."""
    if not isinstance(messages, list) or not messages:
        return ""
    normalized = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "user")
        content = msg.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text))
            content = "\n".join(parts)
        elif content is None:
            content = ""
        else:
            content = str(content)
        if content.strip():
            normalized.append((role, content.strip()))
    if not normalized:
        return ""
    if len(normalized) == 1 and normalized[0][0] == "user":
        return normalized[0][1]
    lines = ["Continue this chat. Answer the latest user message.", ""]
    for role, content in normalized:
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def extract_hermes_final_response(stdout: str) -> str:
    """Best-effort cleanup of Hermes CLI output for API/proxy responses."""
    text = ANSI_RE.sub("", stdout or "").replace("\r\n", "\n")
    for marker in ("\nResume this session with:", "\nSession:", "\nsession_id:"):
        if marker in text:
            text = text.rsplit(marker, 1)[0]
    # Prefer content printed inside the Hermes response box.
    if "╭─ ⚕ Hermes" in text:
        text = text.rsplit("╭─ ⚕ Hermes", 1)[1]
        text = "\n".join(text.split("\n")[1:])
    # Drop common diagnostics/noise while keeping the final answer.
    drop_prefixes = (
        "[neural]", "[embed]", "Embedding backend:", "PASS:", "FAIL:",
        "┌─", "└─", "╰─", "╭─", "─", "⚠️", "❌",
    )
    cleaned = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if stripped.startswith(drop_prefixes):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned).strip()
    # If reasoning leaked before a short final answer, use the last paragraph.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) > 1:
        text = paragraphs[-1]
    return text.strip() or stdout.strip()


# ================================================================
# SESSION STATE
# ================================================================

class SessionManager:
    """Manages encrypted sessions with DLM vault fallback."""
    
    def __init__(self):
        self.sessions = {}  # session_id -> {cm, created, last_active}
        self.default_session = None
    
    def create_session(self) -> dict:
        """Create a new encrypted session."""
        session_id = os.urandom(8).hex()
        cm = CryptoMiddleware()
        cm.session_start()
        rp = RememberProtocol()
        
        # Try DLM vault
        dlm_ok = False
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from dlm_vault import DLMVault
            vault = DLMVault(host=DLM_HOST, port=DLM_PORT)
            if vault.health_check() and vault.store_key(session_id, cm.session_key, ttl=SESSION_TTL):
                dlm_ok = True
        except Exception:
            vault = None
        
        session = {
            "session_id": session_id,
            "cm": cm,
            "remember": rp,
            "remember_header": rp.system_prompt_header(),
            "created": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "dlm_stored": dlm_ok,
            "vault": vault if dlm_ok else None,
        }
        
        self.sessions[session_id] = session
        self.default_session = session
        
        return {
            "session_id": session_id,
            "remember_header": session["remember_header"],
            "provider_transport": "remember::base64",
            "dlm_vault": dlm_ok,
        }
    
    def get_session(self, session_id: str = None) -> dict:
        """Get session by ID or default."""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        return self.default_session
    
    def destroy_session(self, session_id: str) -> bool:
        """Destroy a session and its key."""
        session = self.sessions.pop(session_id, None)
        if session:
            if session.get("vault") and session.get("dlm_stored"):
                try:
                    session["vault"].destroy_key(session_id)
                except Exception:
                    pass
            if self.default_session and self.default_session["session_id"] == session_id:
                self.default_session = None
            return True
        return False
    
    def list_sessions(self) -> list:
        """List all active sessions."""
        return [
            {
                "id": s["session_id"],
                "created": s["created"],
                "last_active": s["last_active"],
                "dlm": s["dlm_stored"],
            }
            for s in self.sessions.values()
        ]


# Global session manager
sessions = SessionManager()


# ================================================================
# COMMAND EXECUTION
# ================================================================

def execute_command(cmd: str, args: str = "", encrypted: bool = False,
                    session_id: str = None) -> dict:
    """
    Execute a command and return result.
    
    Built-in commands:
      status     — gateway + DLM status
      sessions   — list active sessions
      session    — create new session
      kill       — destroy a session
      hermes     — run hermes CLI command
      pulse      — run PULSE search
      shell      — run shell command (LAN only, be careful)
      encrypt    — encrypt a message
      decrypt    — decrypt a message
      chaff      — generate chaff message
      key        — rotate session key
    """
    
    if cmd == "status":
        dlm_ok = False
        dlm_version = "N/A"
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from dlm_vault import DLMVault
            vault = DLMVault(host=DLM_HOST, port=DLM_PORT)
            if vault.health_check():
                dlm_ok = True
                lock = vault._make_locker("version-check")
                dlm_version = str(lock.Version())
        except Exception:
            pass
        
        return {
            "status": "ok",
            "gateway": "running",
            "dlm": "online" if dlm_ok else "offline",
            "dlm_version": dlm_version,
            "provider_transport": "remember::base64",
            "local_crypto": "AES256-GCM",
            "sessions": len(sessions.sessions),
            "time": datetime.now().isoformat(),
        }
    
    elif cmd == "sessions":
        return {"sessions": sessions.list_sessions()}
    
    elif cmd == "session":
        result = sessions.create_session()
        return {"created": result}
    
    elif cmd == "kill":
        # Accept session_id from JSON field OR from args
        target = session_id or args
        if target and sessions.destroy_session(target):
            return {"destroyed": target}
        return {"error": "Session not found"}
    
    elif cmd == "hermes":
        if not args:
            return {"error": "No hermes command provided"}

        env = build_hermes_env()
        try:
            hermes_args, runtime = prepare_hermes_argv(args, env)
        except ValueError as e:
            return {"error": f"Invalid hermes args: {e}"}

        try:
            result = subprocess.run(
                hermes_command() + hermes_args,
                capture_output=True, text=True, timeout=120, env=env
            )
            response = {
                "stdout": result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout,
                "stderr": result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr,
                "exit_code": result.returncode,
            }
            # Useful for debugging the proxy alias without exposing credentials.
            if hermes_args != shlex.split(args):
                response["proxy"] = {
                    "alias_rewritten": True,
                    "model": runtime.get("model"),
                    "provider": runtime.get("provider"),
                    "api_key_present": runtime.get("api_key_present"),
                }
            return response
        except subprocess.TimeoutExpired:
            return {"error": "Hermes command timed out (120s)"}
        except FileNotFoundError:
            return {"error": "hermes not found on PATH"}
    
    elif cmd == "pulse":
        if not args:
            return {"error": "No search topic provided"}
        pulse_script = PULSE_SCRIPT
        if not os.path.exists(pulse_script):
            return {"error": f"PULSE not found at {pulse_script}"}
        try:
            result = subprocess.run(
                ["python3", pulse_script, args, "--depth", "quick", "--emit", "json"],
                capture_output=True, text=True, timeout=60
            )
            return {
                "result": result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "PULSE timed out (60s)"}
    
    elif cmd == "shell":
        if not args:
            return {"error": "No shell command provided"}
        # Safety: block dangerous commands
        dangerous = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "chmod 777"]
        if any(d in args for d in dangerous):
            return {"error": "Blocked dangerous command"}
        try:
            result = subprocess.run(
                args, shell=True,
                capture_output=True, text=True, timeout=30
            )
            return {
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-500:],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Shell command timed out (30s)"}
    
    elif cmd == "encrypt":
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session. Create one first."}
        cm = session["cm"]
        blob, chaff = cm.encrypt_outbound(args)
        result = {
            "encrypted": blob,
            "session_id": session["session_id"],
            "chaff": cm.chaff_message() if chaff else None,
        }
        if encrypted:
            resp_blob = cm.encrypt(json.dumps(result))
            return {"ENC_MSG": resp_blob}
        return result
    
    elif cmd == "decrypt":
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session"}
        cm = session["cm"]
        try:
            plaintext = cm.decrypt(args)
            return {"decrypted": plaintext, "session_id": session["session_id"]}
        except ValueError as e:
            return {"error": str(e)}
    
    elif cmd == "chaff":
        session = sessions.get_session(session_id)
        if session and session.get("remember"):
            rp = session["remember"]
            return {"chaff": rp.chaff_message(), "session_id": session["session_id"]}
        return {"chaff": RememberProtocol().chaff_message(), "session_id": None}
    
    elif cmd == "key":
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session"}
        cm = session["cm"]
        rotation = cm.rotate_key()
        return {
            "rotated": True,
            "rotation_blob": rotation,
            "keys_in_history": len(cm._key_history),
        }
    
    elif cmd == "roundtrip":
        # End-to-end encrypt/decrypt test
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session. Create one first."}
        cm = session["cm"]
        test_msg = args or "roundtrip test"
        blob, chaff = cm.encrypt_outbound(test_msg)
        try:
            decrypted = cm.decrypt(blob)
            return {
                "roundtrip": True,
                "match": decrypted == test_msg,
                "plaintext": test_msg,
                "encrypted": blob,
                "decrypted": decrypted,
                "session_id": session["session_id"],
            }
        except Exception as e:
            return {"roundtrip": False, "error": str(e)}
    
    else:
        return {"error": f"Unknown command: {cmd}", "help": "status, sessions, session, kill, hermes, pulse, shell, encrypt, decrypt, chaff, key, roundtrip"}


# ================================================================
# HTML INTERFACE
# ================================================================

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hermes Gateway</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,monospace;background:#0a0a12;color:#f5b731;min-height:100vh}
.hdr{background:#1a1a24;padding:12px 16px;border-bottom:1px solid #333;display:flex;justify-content:space-between;align-items:center}
.hdr h1{font-size:16px;color:#f5b731}
.hdr .status{font-size:12px;color:#888}
.main{max-width:600px;margin:0 auto;padding:16px}
.card{background:#1a1a24;border:1px solid #333;border-radius:8px;margin-bottom:12px;overflow:hidden}
.card-hdr{padding:10px 14px;border-bottom:1px solid #222;font-size:13px;font-weight:600;color:#f5b731}
.card-body{padding:14px}
input,textarea,select,button{font-family:inherit;font-size:14px}
input,textarea,select{width:100%;background:#0a0a12;color:#f5b731;border:1px solid #333;border-radius:4px;padding:8px 10px;margin-bottom:8px}
input:focus,textarea:focus{outline:none;border-color:#f5b731}
button{background:#f5b731;color:#0a0a12;border:none;border-radius:4px;padding:10px 16px;cursor:pointer;font-weight:600;width:100%;margin-bottom:6px}
button:active{opacity:.8}
button.sec{background:#333;color:#f5b731}
.output{background:#0a0a12;border:1px solid #333;border-radius:4px;padding:10px;font-size:12px;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto;margin-top:8px;color:#ccc}
.qbtn{display:inline-block;background:#222;color:#f5b731;border:1px solid #444;border-radius:4px;padding:6px 10px;margin:3px;cursor:pointer;font-size:12px}
.qbtn:active{background:#f5b731;color:#0a0a12}
.crypto-indicator{font-size:11px;color:#4a4;padding:4px 8px;background:#112211;border-radius:4px;display:inline-block}
</style>
</head>
<body>
<div class="hdr">
  <h1>HERMES</h1>
  <div class="status"><span id="st">connecting...</span></div>
</div>
<div class="main">
  <div class="card">
    <div class="card-hdr">QUICK ACTIONS</div>
    <div class="card-body">
      <span class="qbtn" onclick="run('status')">Status</span>
      <span class="qbtn" onclick="run('sessions')">Sessions</span>
      <span class="qbtn" onclick="run('session')">New Session</span>
      <span class="qbtn" onclick="run('chaff')">Chaff</span>
      <span class="qbtn" onclick="askPulse()">PULSE</span>
      <span class="qbtn" onclick="askHermes()">Hermes</span>
    </div>
  </div>
  <div class="card">
    <div class="card-hdr">COMMAND</div>
    <div class="card-body">
      <select id="cmd">
        <option value="status">status</option>
        <option value="sessions">sessions</option>
        <option value="session">session (new)</option>
        <option value="hermes">hermes</option>
        <option value="pulse">pulse</option>
        <option value="shell">shell</option>
        <option value="encrypt">encrypt</option>
        <option value="decrypt">decrypt</option>
        <option value="chaff">chaff</option>
        <option value="key">key (rotate)</option>
        <option value="roundtrip">roundtrip test</option>
        <option value="kill">kill session</option>
      </select>
      <input id="args" placeholder="arguments (optional)" />
      <button onclick="submit()">EXECUTE</button>
      <div class="crypto-indicator" id="crypto-st">remember:: ready</div>
      <div class="output" id="out">Ready.</div>
    </div>
  </div>
</div>
<script>
let sid=null;
async function api(cmd,args){
  const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({cmd,args,session_id:sid})});
  return r.json();
}
async function run(cmd,args=''){
  const out=document.getElementById('out');
  out.textContent='Running '+cmd+'...';
  try{
    const d=await api(cmd,args);
    out.textContent=JSON.stringify(d,null,2);
    if(d.created&&d.created.session_id){
      sid=d.created.session_id;
      document.getElementById('st').textContent='session:'+sid.slice(0,8);
    }
  }catch(e){out.textContent='Error: '+e.message}
}
async function submit(){
  const cmd=document.getElementById('cmd').value;
  const args=document.getElementById('args').value;
  await run(cmd,args);
}
function askPulse(){
  const t=prompt('PULSE search topic:');
  if(t)run('pulse',t);
}
function askHermes(){
  const t=prompt('Hermes command (e.g. "ask what is 2+2"):');
  if(t)run('hermes',t);
}
// Auto-status on load
run('status');
</script>
</body>
</html>"""


# ================================================================
# HTTP HANDLER
# ================================================================

class GatewayHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the LAN gateway."""
    
    def log_message(self, format, *args):
        """Minimal logging."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0] if args else ''}")
    
    def do_GET(self):
        """Serve web UI or handle GET API calls."""
        path = urlparse(self.path).path
        
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        
        elif path == "/status":
            result = execute_command("status")
            self._json_response(result)
        
        elif path == "/health":
            result = execute_command("status")
            self._json_response({"status": result.get("status", "ok"), "gateway": "running"})

        elif path in {"/v1", "/v1/"}:
            self._json_response({
                "object": "service",
                "id": "wonderland-gateway",
                "status": "ok",
                "endpoints": [
                    "/v1/models",
                    "/v1/chat/completions",
                ],
            })

        elif path == "/v1/models":
            runtime = resolve_wonderland_upstream(os.environ.copy())
            model_id = runtime.get("model") or ""
            provider = runtime.get("provider") or "upstream"
            meta = resolve_upstream_model_meta(runtime)
            models = [
                ("wonderland", "hermes"),
                ("hermes-agent", "hermes"),
                (model_id, provider),
            ]
            seen = set()
            data = []
            for model, owner in models:
                if not model or model in seen:
                    continue
                seen.add(model)
                entry = {"id": model, "object": "model", "owned_by": owner}
                entry.update(meta)
                data.append(entry)
            self._json_response({"object": "list", "data": data})

        elif path == "/sessions":
            result = execute_command("sessions")
            self._json_response(result)
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
    
    def do_OPTIONS(self):
        """CORS preflight for browser/OpenAI-compatible clients."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Hermes-Session-Id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_POST(self):
        """Handle command POSTs and OpenAI-compatible chat completions."""
        path = urlparse(self.path).path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, 400)
            return

        if path == "/v1/chat/completions":
            self._handle_chat_completions(data)
            return

        if path != "/command":
            self._json_response({"error": "Not found"}, 404)
            return
        
        session_id = data.get("session_id")
        token_ok = self._token_ok()

        # Inner AES layer: {session_id, enc:<base64 AES-GCM blob of {cmd,args,...}>}.
        # The gateway is the trusted endpoint here (unlike the upstream provider),
        # so it legitimately decrypts with the session key it shares with a paired,
        # authenticated client. This gives app<->gateway zero-knowledge on the LAN
        # hop, independent of (and underneath) TLS.
        inner_encrypted = False
        if data.get("enc"):
            sess = sessions.get_session(session_id)
            if not sess:
                self._json_response({"error": "No session for encrypted request"}, 401)
                return
            try:
                inner = json.loads(sess["cm"].decrypt(data["enc"]))
            except Exception:
                self._json_response({"error": "Decryption failed"}, 400)
                return
            data = {**data, **inner}
            session_id = data.get("session_id", session_id)
            inner_encrypted = True

        cmd = data.get("cmd", "")
        args = data.get("args", "")
        encrypted = data.get("encrypted", False)

        if not cmd:
            self._json_response({"error": "No 'cmd' field"}, 400)
            return

        # Decrypting a valid inner envelope proves possession of the session key,
        # which is only ever handed to a token-authenticated client, so it counts
        # as authentication too.
        if not (token_ok or inner_encrypted) and self._command_protected(cmd):
            self._json_response(
                {"error": "Unauthorized: this command requires a gateway token"}, 401
            )
            return

        result = execute_command(cmd, args, encrypted, session_id)

        # Client-key handshake: hand the per-session AES key to the authenticated
        # caller so it can drive the encrypted (`enc`) path on subsequent calls.
        # Only for genuinely authenticated callers — never in auth-disabled
        # legacy mode (keeps the tokenless response shape unchanged).
        authed = inner_encrypted or (bool(GATEWAY_TOKEN) and token_ok)
        if cmd == "session" and authed and isinstance(result.get("created"), dict):
            sess = sessions.get_session(result["created"].get("session_id"))
            if sess:
                result["created"]["client_key"] = sess["cm"].session_key

        if inner_encrypted:
            sess = sessions.get_session(session_id)
            if sess:
                self._json_response({"enc": sess["cm"].encrypt(json.dumps(result, default=str))})
                return
        self._json_response(result)

    def _openai_error(self, message: str, code: int = 400, err_type: str = "invalid_request_error"):
        self._json_response({"type": "error", "error": {"type": err_type, "message": message}}, code)

    def _handle_chat_completions(self, data: dict):
        """OpenAI-compatible /v1/chat/completions proxy through Wonderland.

        `model: wonderland` is a local alias.  It is rewritten to the configured
        upstream provider model, while user/tool payloads are encoded with the
        Remember Protocol before they leave the Wonderland pod.  AES headers,
        AES ciphertext, and AES key material are never sent upstream.
        """
        messages = data.get("messages") or []
        if not isinstance(messages, list) or not messages:
            self._openai_error("No messages provided", 400)
            return

        upstream = resolve_wonderland_upstream(os.environ.copy())
        missing = [
            name for name in ("base_url", "model", "api_key")
            if not upstream.get(name)
        ]
        if missing:
            self._openai_error(
                "Wonderland upstream is not configured. Set "
                "WONDERLAND_UPSTREAM_PROVIDER, WONDERLAND_UPSTREAM_MODEL, and "
                "WONDERLAND_UPSTREAM_API_KEY in container/gateway.env.",
                503,
                "server_error",
            )
            return

        session = _session_for_openai_request(self.headers, data)
        requested_model = str(data.get("model") or "wonderland").strip()
        requested_lower = requested_model.lower()
        upstream_model = upstream.get("model") or requested_model
        if requested_lower and requested_lower not in PROXY_MODEL_ALIASES:
            upstream_model = requested_model

        payload = dict(data)
        payload["model"] = upstream_model
        payload["messages"] = remember_openai_messages(session, messages)
        url = upstream["base_url"].rstrip("/") + "/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {upstream['api_key']}",
            "X-Title": "Wonderland Gateway",
        }
        if upstream.get("provider") == "openrouter":
            headers["HTTP-Referer"] = "http://127.0.0.1:18080"

        request = Request(url, data=body, headers=headers, method="POST")
        try:
            upstream_response = urlopen(request, timeout=1800)
        except HTTPError as e:
            message = e.read().decode("utf-8", errors="replace")[-2000:] or str(e)
            self._openai_error(message, e.code, "server_error")
            return
        except URLError as e:
            self._openai_error(f"Wonderland upstream connection failed: {e}", 502, "server_error")
            return

        if data.get("stream"):
            self._proxy_sse_response(upstream_response)
            return

        raw = upstream_response.read().decode("utf-8", errors="replace")
        try:
            response_data = json.loads(raw)
        except json.JSONDecodeError:
            self._openai_error(raw[-2000:] or "Invalid upstream JSON", 502, "server_error")
            return
        response_data = decode_openai_response(session, response_data)
        response_data["model"] = requested_model or "wonderland"
        self._json_response(response_data)

    def _proxy_sse_response(self, upstream_response):
        """Stream an upstream SSE response without running an agent in the pod."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        while True:
            chunk = upstream_response.read(8192)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    def _sse_chat_response(self, completion_id: str, model: str, created: int, content: str):
        """Emit a minimal OpenAI-compatible SSE stream after Hermes completes."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        chunks = [
            {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model,
             "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]},
            {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model,
             "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]},
            {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model,
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        for chunk in chunks:
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
    
    def _token_ok(self) -> bool:
        """True if the request carries the configured gateway token, or if no
        token is configured at all (auth disabled — legacy/dev/localhost)."""
        if not GATEWAY_TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            presented = auth[7:].strip()
        else:
            presented = self.headers.get("X-Gateway-Token", "").strip()
        if not presented:
            return False
        return secrets.compare_digest(presented, GATEWAY_TOKEN)

    @staticmethod
    def _command_protected(cmd: str) -> bool:
        return bool(GATEWAY_TOKEN) and cmd.strip().lower() in PROTECTED_COMMANDS

    def _json_response(self, data: dict, code: int = 200):
        """Send JSON response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())


# ================================================================
# RAW TCP HANDLER (netcat compatible)
# ================================================================

def raw_tcp_server(port: int):
    """Simple raw TCP server for netcat compatibility."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(5)
    print(f"[TCP] Raw TCP on :{port} (netcat compatible)")
    
    while True:
        try:
            conn, addr = sock.accept()
            threading.Thread(target=_handle_tcp, args=(conn, addr), daemon=True).start()
        except Exception:
            pass


def _handle_tcp(conn: socket.socket, addr: tuple):
    """Handle a raw TCP connection."""
    try:
        conn.settimeout(10)
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        
        line = data.decode("utf-8").strip()
        if not line:
            conn.close()
            return
        
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            # Treat as shell command
            request = {"cmd": "shell", "args": line}
        
        cmd = request.get("cmd", "shell")
        args = request.get("args", "")
        session_id = request.get("session_id")

        # Raw TCP carries the token as a JSON field. Protected commands are
        # refused without it once a token is configured.
        if GATEWAY_TOKEN and cmd.strip().lower() in PROTECTED_COMMANDS:
            presented = str(request.get("token", ""))
            if not (presented and secrets.compare_digest(presented, GATEWAY_TOKEN)):
                conn.sendall(json.dumps({"error": "Unauthorized: token required"}).encode() + b"\n")
                conn.close()
                return

        result = execute_command(cmd, args, session_id=session_id)
        
        response = json.dumps(result, default=str) + "\n"
        conn.sendall(response.encode())
    except Exception as e:
        try:
            conn.sendall(json.dumps({"error": str(e)}).encode() + b"\n")
        except Exception:
            pass
    finally:
        conn.close()


# ================================================================
# MAIN
# ================================================================

class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    """Threading server that can restart immediately after a deploy."""
    allow_reuse_address = True
    daemon_threads = True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Zero-Knowledge LAN Gateway")
    parser.add_argument("--port", type=int, default=GATEWAY_PORT, help="HTTP port")
    parser.add_argument("--tcp-port", type=int, default=RAW_TCP_PORT, help="Raw TCP port")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address")
    parser.add_argument("--no-crypto", action="store_true", help="Disable encryption")
    parser.add_argument("--tls-cert", default=GATEWAY_TLS_CERT, help="TLS certificate (PEM)")
    parser.add_argument("--tls-key", default=GATEWAY_TLS_KEY, help="TLS private key (PEM)")
    parser.add_argument("--no-tls", action="store_true", help="Force plaintext HTTP even if a cert exists")
    args = parser.parse_args()

    tls_enabled = (
        not args.no_tls
        and os.path.exists(args.tls_cert)
        and os.path.exists(args.tls_key)
    )
    scheme = "https" if tls_enabled else "http"

    print("=" * 50)
    print("  HERMES ZERO-KNOWLEDGE LAN GATEWAY")
    print("=" * 50)
    print(f"  HTTP:  {scheme}://{args.bind}:{args.port}")
    print(f"  TCP:   {args.bind}:{args.tcp_port} (netcat)")
    print(f"  Transport: {'DISABLED' if args.no_crypto else 'remember:: (base64) → provider'}")
    print(f"  TLS:   {'ENABLED (' + args.tls_cert + ')' if tls_enabled else 'DISABLED (plaintext LAN)'}")
    print(f"  Auth:  {'TOKEN REQUIRED on ' + ','.join(sorted(PROTECTED_COMMANDS)) if GATEWAY_TOKEN else 'OPEN (no token configured)'}")
    print(f"  DLM:   {DLM_HOST}:{DLM_PORT}")
    print("=" * 50)
    
    # Start raw TCP server in background
    tcp_thread = threading.Thread(target=raw_tcp_server, args=(args.tcp_port,), daemon=True)
    tcp_thread.start()
    
    # Create default session
    if not args.no_crypto:
        result = sessions.create_session()
        print(f"  Default session: {result['session_id']}")
        print(f"  DLM vault: {'YES' if result['dlm_vault'] else 'NO (memory only)'}")
    
    print()
    print("  Access from any LAN device:")
    print(f"  Browser: http://<this-ip>:{args.port}")
    print(f"  curl:    curl -X POST http://<this-ip>:{args.port}/command -d '{{\"cmd\":\"status\"}}'")
    print(f"  netcat:  echo '{{\"cmd\":\"status\"}}' | nc <this-ip> {args.tcp_port}")
    print()
    
    # Start HTTP(S) server
    with ReusableThreadingTCPServer((args.bind, args.port), GatewayHandler) as httpd:
        if tls_enabled:
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(args.tls_cert, args.tls_key)
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
