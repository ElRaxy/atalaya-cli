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

1. Aggregates remote dev offers from **8 working job boards + 1 parser-ready** (Indeed ES,
   blocked by Cloudflare on direct HTTP — Playwright fallback planned but not shipped).
2. Deduplicates and stores them locally (SQLite).
3. Scores each offer against your profile (stack, seniority, location).
4. Generates tailored cover letters and CV variants with the Claude API.
5. Exports shortlists to CSV/JSON for manual review.
6. **Applies automatically** to offers exposing a contact email (SMTP). Rate-limited
   (1 application / 5 minutes by default) to avoid spam detection.

### Install

Not on PyPI yet, so install from source:

```bash
git clone https://github.com/ElRaxy/atalaya-cli && cd atalaya-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Then install the agent skill into your AI coding CLI (Claude Code, Codex, OpenCode):

```bash
bhound skill install
```

### Quickstart

```bash
bhound init
bhound search --board all --remote-only
bhound list --min-score 60
bhound letter <offer-id>
bhound cv <offer-id>
bhound apply <offer-id> --preview               # dry-run, check email target
bhound apply <offer-id>                         # send email (offers with contact email)
bhound apply-manual <offer-id>                  # for form-only offers: copy letter, open browser
bhound apply-manual <offer-id> --mark-applied   # re-run to record APPLIED in DB
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

Typical run yields **~300 offers across 8 working boards** before scoring + deduplication.
`indeed_es` returns 0 offers until the Playwright fallback ships.

### AI generators

Atalaya uses the Anthropic API (Claude) to generate tailored cover letters and CV variants per offer. Prompt caching is enabled on the system prompt to reduce cost across multiple calls in the same session.

```bash
bhound letter 3 --lang es
bhound letter 3 --lang en --tone warm --out applications/zendrop-letter.md
bhound cv 3 --lang en --out applications/zendrop-cv.md
bhound export --fmt csv --out shortlist
```

### Claude backend (CLI vs API)

Atalaya supports two ways to talk to Claude. The default is **CLI** — it spawns
`claude -p` as a subprocess and rides on your existing Claude Code subscription
(Pro / Max / Team) via the OAuth keychain. No `ANTHROPIC_API_KEY` required, no
extra billing.

```toml
[claude]
backend = "cli"                   # default — uses Claude Code subscription
model   = "claude-sonnet-4-6"     # also supports claude-haiku-4-5-20251001, claude-opus-4-7
```

Override per-call with the env var `ATALAYA_CLAUDE_BACKEND=api|cli`.

To use the **API** backend (your own `ANTHROPIC_API_KEY`, separate billing):

```bash
pip install -e ".[api]"
```

Then in `config.toml`:

```toml
[claude]
backend = "api"

[anthropic]
api_key = "sk-ant-..."
```

(`ANTHROPIC_API_KEY` env var is also picked up.)

The `cv` command reads the base CV from `projects/job-search/cv/cv-{lang}.md` by default
(relative to the directory you run `bhound` from). Override with the env var
`ATALAYA_BASE_CV_DIR` (absolute path to the directory containing `cv-es.md` / `cv-en.md`)
or the per-call flag `--cv-base PATH`. The file format is plain Markdown — Atalaya passes
it verbatim to the Claude API as the base CV to tailor against each offer.

### Automatic apply (M6)

Atalaya can send your cover letter + CV variant by email to offers that expose a contact address.
The expected flow is **`letter` → `cv` → `apply`** — `apply` recovers the persisted letter and
CV variant from the local SQLite and reuses them. If neither has been generated for the offer,
`apply` emits a warning and falls back to a short generic body without attachment.

```bash
bhound letter 42                 # generate tailored cover letter (saved to DB)
bhound cv 42                     # generate tailored CV variant   (saved to DB, preserves letter)
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

### Manual-assisted apply (for forms-only offers)

LinkedIn, InfoJobs, Tecnoempleo and most company portals require their own form
(no email exposed). Atalaya helps you apply to those in ~30s per offer **without
any automation against the platform** (zero ban risk):

```bash
bhound apply-manual 42                   # prepares dossier, opens browser
# (paste letter in the form, attach CV, click Submit yourself)
bhound apply-manual 42 --mark-applied    # re-run to record APPLIED in DB
```

What it does:

1. Recovers the persisted letter + CV variant from SQLite.
2. Writes both to `<tmp>/atalaya-apply-<id>/{letter.md,cv.md}` (paths printed).
3. Copies the cover letter to your system clipboard (Windows `clip` / macOS
   `pbcopy` / Linux `xclip`/`xsel`/`wl-copy`).
4. Opens the offer URL in your default browser.
5. You paste, attach the CV file, click Submit in the browser.
6. Re-run with `--mark-applied` to mark the offer as APPLIED in the DB.

**Automated LinkedIn Easy Apply / InfoJobs Playwright are intentionally not implemented**
(ADR-0047, 2026-05-16). Selenium/Playwright against anti-bot detection is brittle and
carries real ban risk on a personal account.

### External tools (LinkedIn Easy Apply)

Atalaya is intentionally email-apply-only. If you need LinkedIn Easy Apply automation,
combine Atalaya (scoring + tailored letters + CV variants) with one of these external tools:

- **Manual outreach to recruiters** — empirically more effective than mass Easy Apply.
- **Simplify.jobs** (free Chrome extension) — autofills forms per-offer.
- **LazyApply** (paid SaaS, ~$129) — mass Easy Apply for LinkedIn.

These run independently; Atalaya does not depend on or integrate with any of them.

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

1. Agrega ofertas dev remoto desde **8 job boards operativos + 1 parser-ready** (Indeed ES,
   bloqueado por Cloudflare en HTTP directo — fallback Playwright planeado, no enviado).
2. Deduplica y almacena localmente (SQLite).
3. Puntúa cada oferta contra tu perfil (stack, seniority, ubicación).
4. Genera cartas de presentación y variantes de CV personalizadas con la API de Claude.
5. Exporta shortlists a CSV/JSON para revisión manual.
6. **Aplica automáticamente** a ofertas con email de contacto (SMTP). Rate-limited
   (1 envío / 5 min por defecto) para evitar detección como spam.

### Instalación

Todavía no está en PyPI, así que se instala desde el código:

```bash
git clone https://github.com/ElRaxy/atalaya-cli && cd atalaya-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Y para instalar la skill de agente en tu CLI (Claude Code, Codex, OpenCode):

```bash
bhound skill install
```

### Uso rápido

```bash
bhound init
bhound search --board all --remote-only
bhound list --min-score 60
bhound letter <id-oferta>
bhound cv <id-oferta>
bhound apply <id-oferta> --preview              # dry-run, verifica email destino
bhound apply <id-oferta>                        # envía email (ofertas con email contacto)
bhound apply-manual <id-oferta>                 # ofertas con form: copia carta, abre navegador
bhound apply-manual <id-oferta> --mark-applied  # re-ejecuta para registrar APPLIED en BD
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

Un run típico produce **~300 ofertas across 8 boards operativos** antes de scoring + dedup.
`indeed_es` devuelve 0 ofertas hasta que llegue el fallback Playwright.

### Generadores IA

Atalaya utiliza la API de Anthropic (Claude) para generar cartas de presentación y variantes de CV adaptadas a cada oferta. El prompt caching está activo en el system prompt para reducir coste entre llamadas sucesivas.

```bash
bhound letter 3 --lang es
bhound letter 3 --lang en --tone warm --out applications/zendrop-letter.md
bhound cv 3 --lang en --out applications/zendrop-cv.md
bhound export --fmt csv --out shortlist
```

### Backend Claude (CLI vs API)

Atalaya soporta dos formas de hablar con Claude. El default es **CLI** — lanza
`claude -p` por subprocess y reutiliza tu suscripción Claude Code (Pro / Max /
Team) vía OAuth keychain. **Sin `ANTHROPIC_API_KEY`, sin facturación extra.**

```toml
[claude]
backend = "cli"                   # default — tira de tu suscripción Claude Code
model   = "claude-sonnet-4-6"     # también claude-haiku-4-5-20251001, claude-opus-4-7
```

Override por llamada con `ATALAYA_CLAUDE_BACKEND=api|cli`.

Para usar el backend **API** (tu propia `ANTHROPIC_API_KEY`, facturación aparte):

```bash
pip install -e ".[api]"
```

Y en `config.toml`:

```toml
[claude]
backend = "api"

[anthropic]
api_key = "sk-ant-..."
```

(`ANTHROPIC_API_KEY` env var también se reconoce.)

El comando `cv` lee el CV base de `projects/job-search/cv/cv-{lang}.md` por defecto
(relativo al directorio desde el que se ejecuta `bhound`). Se puede sobrescribir con la
variable de entorno `ATALAYA_BASE_CV_DIR` (path absoluto a la carpeta con `cv-es.md` /
`cv-en.md`) o el flag `--cv-base PATH` por llamada. El formato es Markdown plano —
Atalaya lo pasa textual a la API de Claude como el CV base que adaptar a cada oferta.

### Apply automático (M6)

Atalaya puede enviar tu carta + variante CV por email a ofertas que expongan dirección de contacto.
El flujo esperado es **`letter` → `cv` → `apply`** — `apply` recupera la carta y el CV
persistidos en SQLite y los reutiliza. Si no se han generado para la oferta, `apply` emite
un warning y cae al cuerpo genérico corto sin adjunto.

```bash
bhound letter 42                 # genera carta tailored (guardada en DB)
bhound cv 42                     # genera CV variant     (guardado en DB, preserva carta)
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

### Apply manual asistido (ofertas con formulario)

LinkedIn, InfoJobs, Tecnoempleo y la mayoría de portales de empresa usan formulario
propio (sin email expuesto). Atalaya te ayuda a aplicar a esas en ~30s por oferta
**sin automation contra la plataforma** (cero riesgo de ban):

```bash
bhound apply-manual 42                   # prepara dossier, abre navegador
# (pegas carta en form, adjuntas CV, clicas Submit tú mismo)
bhound apply-manual 42 --mark-applied    # re-ejecuta para registrar APPLIED en BD
```

Qué hace:

1. Recupera carta + CV variant persistidos en SQLite.
2. Escribe ambos a `<tmp>/atalaya-apply-<id>/{letter.md,cv.md}` (rutas en stdout).
3. Copia la carta al portapapeles del sistema (Windows `clip` / macOS `pbcopy` /
   Linux `xclip`/`xsel`/`wl-copy`).
4. Abre la URL de la oferta en tu navegador por defecto.
5. Tú pegas, adjuntas el CV, clicas Submit en el navegador.
6. Re-ejecutas con `--mark-applied` para registrar la oferta como APPLIED en BD.

**LinkedIn Easy Apply / InfoJobs Playwright automatizados se han descartado**
intencionalmente (ADR-0047, 2026-05-16). Selenium/Playwright contra anti-bot detection
es frágil y supone riesgo real de ban en cuenta personal.

### Herramientas externas (LinkedIn Easy Apply)

Atalaya es email-apply-only por diseño. Si necesitas Easy Apply LinkedIn, combina Atalaya
(scoring + cartas + CVs tailored) con alguna tool externa:

- **Outreach manual a recruiters** — empíricamente más efectivo que Easy Apply masivo.
- **Simplify.jobs** (extensión Chrome gratis) — autofill formularios uno a uno.
- **LazyApply** (SaaS pago, ~$129) — Easy Apply masivo LinkedIn.

Funcionan de forma independiente; Atalaya no depende ni integra con ninguna.

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
