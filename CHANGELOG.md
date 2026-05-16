# Changelog

All notable changes to **atalaya-cli** are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Claude Code subprocess backend (default)** — Atalaya tira de la suscripción
  Claude Code (Pro / Max / Team) vía OAuth keychain. Sin `ANTHROPIC_API_KEY`,
  sin facturación extra. `[claude] backend = "cli"` en `config.toml`. Backend
  histórico API queda como opt-in via `pip install atalaya-cli[api]`.
- **`bhound apply-manual <id>`** — apply asistido para ofertas con formulario
  (LinkedIn / InfoJobs / portales empresa). Prepara dossier en tmp dir, copia
  la carta al clipboard, abre la URL en navegador. Cero automation contra la
  plataforma → cero riesgo de ban. Flag `--mark-applied` para registrar APPLIED
  en BD tras el submit manual.
- **Description enrichment en RemoteOK + WWR** — los scrapers ahora pueblan
  `Offer.description` con HTML stripped del payload, lo que permite a
  `EmailApplier` extraer emails de contacto cuando la oferta los expone (subida
  significativa del % auto-applicable real).

### Changed

- `anthropic` SDK movido a optional dependency (`[api]`). La instalación base
  no lo trae.

### Fixed

- (Ya en 0.1.0 pero re-listado por claridad): bug #1 `apply` ignoraba carta+CV
  persistidos; bug #2 `letter`/`cv` se machacaban mutuamente.

## [0.1.0] — 2026-05-16

Initial alpha release. Functional end-to-end pipeline: scrape → score → tailored
letter/CV via Claude API → email apply (with rate-limit) → IMAP ingest of job
alerts.

### Added

- **CLI binary `bhound`** with commands `init`, `search`, `list`, `letter`, `cv`,
  `apply`, `apply-batch`, `ingest-email`, `export`, `version`.
- **8 working scrapers** (`remoteworkspain`, `jobfluent`, `himalayas`, `remoteok`,
  `weworkremotely`, `tecnoempleo`, `infojobs`, `linkedin_public`) + 1 parser-ready
  but Cloudflare-blocked (`indeed_es`).
- **Scoring** of each offer against the user profile (stack, remote, seniority,
  language, freshness modifier) with weighted breakdown 0-100.
- **AI generators** for tailored cover letters and CV variants using
  `claude-sonnet-4-6` with prompt caching on the system block.
- **Email applier** (`appliers/email_apply.py`): extracts contact email from
  description (regex + blocklist), sends SMTP with letter + CV markdown
  attachment, respects persistent rate-limit (5 min default + ±90s jitter).
- **IMAP ingest** (`bhound ingest-email`): reads job alert emails (LinkedIn /
  InfoJobs / Tecnoempleo / RemoteOK) via stdlib `imaplib`, parses HTML cards,
  upserts offers. Idempotent via `email_seen` table (Message-ID dedupe).
- **SQLite storage** with `offers`, `applications`, `runs`, `email_seen` tables.
- **GitHub Actions CI** — ruff + mypy strict + pytest (matrix Python 3.12, 3.13).
- **README** bilingual EN / ES with quickstart, board table, SMTP/IMAP config,
  external tools section.

### Fixed (relative to alpha snapshots during the sprint)

- `bhound apply` now recovers persisted `letter_md` and `cv_variant_md` from the
  `applications` table instead of starting with an empty draft.
- `bhound letter` and `bhound cv` no longer overwrite each other's fields on
  upsert (new `merge_application` helper preserves existing non-empty fields).

### Decided

- **LinkedIn Easy Apply (Playwright) intentionally out of scope** (ADR-0047,
  2026-05-16). AIHawk (29.8k stars, the obvious open-source candidate to wrap)
  was archived 2026-04-16 and licensed AGPL-3.0 (incompatible with Atalaya's
  MIT). Selenium/Playwright against LinkedIn's anti-bot is brittle and carries
  ban risk on the user's personal account. Manual outreach to recruiters is
  empirically more effective for the target use case.

### Known limitations

- `indeed_es` scraper is parser-ready but blocked by Cloudflare on direct HTTP.
  Counts as a board only when Playwright fallback ships.
- `bhound apply` emits a warning but does not block when no letter/CV variant
  exist for the offer — the email body falls back to a short generic message
  without attachment.
- No automatic LinkedIn / InfoJobs form submission (Playwright path
  intentionally skipped — see Decided).
- Coverage 76% project-wide; `cli.py` and `imap_client.py` paths against real
  external services are mocked, not exercised live.

[Unreleased]: https://github.com/ElRaxy/atalaya-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ElRaxy/atalaya-cli/releases/tag/v0.1.0
