# Atalaya

> Tu vigía de ofertas dev remoto. AI-powered job aggregator CLI.

[![CI](https://github.com/ElRaxy/atalaya-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/ElRaxy/atalaya-cli/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy_strict-blue.svg)](http://mypy-lang.org/)

**Atalaya** scrapes dev job boards, scores offers against your profile, generates tailored cover letters with Claude, and applies on your behalf (email + Playwright forms). Built for remote devs in Spain/EU hunting their next role.

[English](#english) · [Español](#español)

---

## English

### What

`atalaya-cli` is a Python CLI that:

1. Aggregates remote dev offers from **9 job boards** (Spanish + EU + global remote).
2. Deduplicates and stores them locally (SQLite).
3. Scores each offer against your profile (stack, seniority, location).
4. Generates tailored cover letters and CV variants with the Claude API.
5. Exports shortlists to CSV/JSON for manual review.
6. **Applies automatically** to offers exposing a contact email (SMTP). Rate-limited
   (1 application / 5 minutes by default) to avoid spam detection.

### Install

```bash
pip install atalaya-cli
```

### Quickstart

```bash
bhound init
bhound search --board all --remote-only
bhound list --min-score 60
bhound letter <offer-id>
bhound cv <offer-id>
bhound apply <offer-id> --preview          # dry-run, check target without sending
bhound apply <offer-id>                    # really send (rate-limited 5 min)
bhound apply-batch --min-score 70 --limit 5
```

### Supported job boards

| Board              | Source                                         | Notes                                                                  |
| ------------------ | ---------------------------------------------- | ---------------------------------------------------------------------- |
| `remoteworkspain`  | remoteworkspain.es                             | JSON-LD JobPosting on detail pages.                                    |
| `jobfluent`        | jobfluent.com                                  | Server-side HTML. Barcelona/EU startup jobs.                           |
| `himalayas`        | himalayas.app (country=Spain)                  | Remote-first. Next.js SSR HTML.                                        |
| `indeed_es`        | es.indeed.com                                  | Blocked by Cloudflare on direct HTTP. Parser ready for Playwright.     |
| `remoteok`         | remoteok.com (JSON API)                        | Worldwide / Europe / EMEA. Dev-only filter.                            |
| `weworkremotely`   | weworkremotely.com (RSS)                       | 4 programming categories. Excludes USA-only.                           |
| `tecnoempleo`      | tecnoempleo.com                                | Spanish dev jobs, remote filter.                                       |
| `infojobs`         | infojobs.net                                   | Spain generalist. First 5 cards per listing (JS scroll for the rest).  |
| `linkedin_public`  | linkedin.com/jobs-guest                        | No auth. Spain + remote (`f_WT=2`). ~25 offers/run.                    |

Run one board with `--board <name>` or all in parallel with `--board all`.

Typical run yields **~300 offers across 9 boards** before scoring + deduplication.

### AI generators

Atalaya uses the Anthropic API (Claude) to generate tailored cover letters and CV variants per offer. Prompt caching is enabled on the system prompt to reduce cost across multiple calls in the same session.

```bash
bhound letter 3 --lang es
bhound letter 3 --lang en --tone warm --out applications/zendrop-letter.md
bhound cv 3 --lang en --out applications/zendrop-cv.md
bhound export --fmt csv --out shortlist
```

Requires an `ANTHROPIC_API_KEY` either via environment variable or in `~/Library/Application Support/atalaya/config.toml`:

```toml
[anthropic]
api_key = "sk-ant-..."
```

The `cv` command reads the base CV from `projects/job-search/cv/cv-{lang}.md` by default. Override with `ATALAYA_BASE_CV_DIR` or `--cv-base PATH`.

### Automatic apply (M6)

Atalaya can send your cover letter + CV variant by email to offers that expose a contact address:

```bash
bhound apply 42 --preview        # show what would happen, no email sent
bhound apply 42                  # actually send (5-min rate-limit enforced)
bhound apply-batch --min-score 70 --limit 5
```

SMTP config in `<config_dir>/config.toml`:

```toml
[smtp]
host = "smtp.gmail.com"
port = 587
user = "you@example.com"
password = "<gmail-app-password>"   # NEVER your real password — use App Passwords
from_name = "Alex Mico"
from_email = "you@example.com"
starttls = true
```

**Rate-limit**: persistent across CLI invocations, 5 min between applies + random jitter (±90s).
Override with `--force` (carries detection risk).

**LinkedIn Easy Apply / InfoJobs forms** (Playwright) are planned for M6.2 — currently
only email-based apply is supported. For the others, `bhound list` + manual click.

### Email ingest (M7)

Atalaya also reads job alert emails from your inbox (LinkedIn / InfoJobs / Tecnoempleo / RemoteOK)
via IMAP and pushes the offers into SQLite. Idempotent: each `Message-ID` is recorded in
`email_seen`, so re-running won't double-import.

```bash
bhound ingest-email --folder INBOX --since-days 7
```

IMAP config in `<config_dir>/config.toml`:

```toml
[imap]
host = "imap.gmail.com"
port = 993
user = "you@example.com"
password = "<gmail-app-password>"   # same App Password used for SMTP works here
use_ssl = true
```

The 4 supported parsers (`email_linkedin`, `email_infojobs`, `email_tecnoempleo`,
`email_remoteok`) auto-dispatch by `From` header. Unknown senders are skipped.

### Status

Alpha. 9 scrapers operational, AI generators working, email apply working, email IMAP
ingest working, Playwright appliers pending. See [roadmap](../../projects/atalaya/ai/plan.md).

### License

MIT

---

## Español

### Qué es

`atalaya-cli` es un CLI Python que:

1. Agrega ofertas dev remoto desde **9 job boards** (España + EU + global remote).
2. Deduplica y almacena localmente (SQLite).
3. Puntúa cada oferta contra tu perfil (stack, seniority, ubicación).
4. Genera cartas de presentación y variantes de CV personalizadas con la API de Claude.
5. Exporta shortlists a CSV/JSON para revisión manual.
6. **Aplica automáticamente** a ofertas con email de contacto (SMTP). Rate-limited
   (1 envío / 5 min por defecto) para evitar detección como spam.

### Instalación

```bash
pip install atalaya-cli
```

### Uso rápido

```bash
bhound init
bhound search --board all --remote-only
bhound list --min-score 60
bhound letter <id-oferta>
bhound cv <id-oferta>
bhound apply <id-oferta> --preview         # dry-run, verifica destinatario
bhound apply <id-oferta>                   # envía de verdad (rate-limit 5 min)
bhound apply-batch --min-score 70 --limit 5
```

### Job boards soportados

| Board              | Fuente                                          | Notas                                                                  |
| ------------------ | ----------------------------------------------- | ---------------------------------------------------------------------- |
| `remoteworkspain`  | remoteworkspain.es                              | JSON-LD JobPosting en páginas de detalle.                              |
| `jobfluent`        | jobfluent.com                                   | HTML server-side. Startups Barcelona/EU.                               |
| `himalayas`        | himalayas.app (country=Spain)                   | Remote-first. Next.js SSR.                                             |
| `indeed_es`        | es.indeed.com                                   | Bloqueado por Cloudflare en HTTP directo. Parser listo para Playwright.|
| `remoteok`         | remoteok.com (JSON API)                         | Worldwide / Europe / EMEA. Filtro dev-only.                            |
| `weworkremotely`   | weworkremotely.com (RSS)                        | 4 categorías programación. Excluye USA-only.                           |
| `tecnoempleo`      | tecnoempleo.com                                 | Dev jobs ES, filtro remoto.                                            |
| `infojobs`         | infojobs.net                                    | Generalista ES. Primeras 5 cards (resto JS scroll).                    |
| `linkedin_public`  | linkedin.com/jobs-guest                         | Sin auth. Spain + remoto (`f_WT=2`). ~25 ofertas/run.                  |

Usa `--board <nombre>` para uno solo o `--board all` para correrlos en paralelo.

Un run típico produce **~300 ofertas across 9 boards** antes de scoring + dedup.

### Generadores IA

Atalaya utiliza la API de Anthropic (Claude) para generar cartas de presentación y variantes de CV adaptadas a cada oferta. El prompt caching está activo en el system prompt para reducir coste entre llamadas sucesivas.

```bash
bhound letter 3 --lang es
bhound letter 3 --lang en --tone warm --out applications/zendrop-letter.md
bhound cv 3 --lang en --out applications/zendrop-cv.md
bhound export --fmt csv --out shortlist
```

Requiere `ANTHROPIC_API_KEY` bien como variable de entorno o en `~/Library/Application Support/atalaya/config.toml`:

```toml
[anthropic]
api_key = "sk-ant-..."
```

El comando `cv` lee el CV base de `projects/job-search/cv/cv-{lang}.md` por defecto. Se puede sobrescribir con `ATALAYA_BASE_CV_DIR` o `--cv-base PATH`.

### Apply automático (M6)

Atalaya puede enviar tu carta + variante CV por email a ofertas que expongan dirección de contacto:

```bash
bhound apply 42 --preview        # muestra qué pasaría, no envía
bhound apply 42                  # envía de verdad (rate-limit 5 min activo)
bhound apply-batch --min-score 70 --limit 5
```

Configuración SMTP en `<config_dir>/config.toml`:

```toml
[smtp]
host = "smtp.gmail.com"
port = 587
user = "tu@example.com"
password = "<gmail-app-password>"   # NUNCA tu password real — usa App Password
from_name = "Alex Mico"
from_email = "tu@example.com"
starttls = true
```

**Rate-limit**: persistente entre invocaciones CLI, 5 min entre applies + jitter aleatorio (±90s).
Saltable con `--force` (riesgo de detección).

**LinkedIn Easy Apply / InfoJobs forms** (Playwright) — planeados M6.2. Por ahora solo email apply.

### Ingesta de email (M7)

Atalaya también lee alertas de empleo desde tu bandeja (LinkedIn / InfoJobs / Tecnoempleo / RemoteOK)
por IMAP y vuelca las ofertas a SQLite. Idempotente: cada `Message-ID` se registra en
`email_seen` — re-ejecutar no duplica.

```bash
bhound ingest-email --folder INBOX --since-days 7
```

Configuración IMAP en `<config_dir>/config.toml`:

```toml
[imap]
host = "imap.gmail.com"
port = 993
user = "tu@example.com"
password = "<gmail-app-password>"   # mismo App Password que usas para SMTP sirve aquí
use_ssl = true
```

Los 4 parsers soportados (`email_linkedin`, `email_infojobs`, `email_tecnoempleo`,
`email_remoteok`) se auto-asignan por el header `From`. Remitentes desconocidos se ignoran.

### Estado

Alpha. 9 scrapers operativos, generadores IA funcionando, apply por email funcionando,
ingesta IMAP funcionando, appliers Playwright pendientes. Ver [roadmap](../../projects/atalaya/ai/plan.md).

### Licencia

MIT
