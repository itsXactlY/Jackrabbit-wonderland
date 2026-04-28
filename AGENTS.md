# Repository Guidelines

## Project Structure & Module Organization

This repository is a standalone Python 3 encryption layer for Hermes Agent. Core modules live at the repository root: `crypto_middleware.py` handles AES256-GCM operations, `dlm_vault.py` bridges to JackrabbitDLM, `crypto_plugin.py` integrates with Hermes, `lan_gateway.py` exposes HTTP/TCP controls, and `remember_protocol.py` implements the remember transport. Tests are in `tests/` and mirror these components. Production documentation is in `docs/`, with deployment units in `systemd/`. Use `README.md`, `SPEC.md`, and `USECASES.md` for product context before changing behavior.

## Build, Test, and Development Commands

- `python3 tests/run_all.py`: run all test suites.
- `python3 tests/run_all.py crypto`: run middleware encryption tests.
- `python3 tests/run_all.py gateway`: run LAN gateway stress tests.
- `python3 tests/run_all.py dlm`: run DLM vault tests.
- `python3 tests/run_all.py plugin`: run Hermes plugin tests.
- `bash install.sh --check`: verify local service, dependency, firewall, and gateway setup.
- `sudo bash install.sh`: install pycryptodome, JackrabbitDLM, systemd units, and LAN firewall rules.

There is no package manager config in this repo; runtime dependency installation is handled by `install.sh`.

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation. Follow existing naming: modules and functions use `snake_case`, classes use `PascalCase`, and constants use `UPPER_SNAKE_CASE`. Keep top-level scripts executable with `#!/usr/bin/env python3` when they are intended to run directly. Prefer stdlib APIs unless the project already depends on the library. Add type hints where they clarify interfaces, especially for public methods.

## Testing Guidelines

Tests are standalone Python scripts, not pytest modules. Name new files `tests/test_<component>.py` and test functions `test_<behavior>()`. Use `tests/run_all.py` for suite orchestration and add new suites to its `SUITES` map. Cover cryptographic round trips, tamper detection, TTL/key lifecycle behavior, gateway concurrency, and failure paths when changing those areas.

## Commit & Pull Request Guidelines

Recent history uses short, descriptive subjects with optional Conventional Commit-style prefixes, for example `docs: ...`, `test: ...`, `feat: ...`, and `security: ...`. Keep commits focused and mention security-sensitive behavior explicitly. Pull requests should include a brief purpose, affected modules, test commands run, deployment or firewall impact, and linked issues when applicable. Include screenshots only for gateway UI changes.

## Security & Configuration Tips

Do not commit `.env`, local keys, service secrets, or generated runtime state. Treat `docs/security.md` and `docs/configuration.md` as required reading before changing encryption, key storage, gateway exposure, or firewall behavior.
