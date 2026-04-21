# Atalaya

> Tu vigía de ofertas dev remoto. AI-powered job aggregator CLI.

**Atalaya** scrapes dev job boards, scores offers against your profile and generates tailored cover letters with Claude. Built for remote devs in Spain/EU hunting their next role.

[English](#english) · [Español](#español)

---

## English

### What

`atalaya-cli` is a Python CLI that:

1. Aggregates remote dev offers from multiple Spanish/EU job boards.
2. Deduplicates and stores them locally (SQLite).
3. Scores each offer against your profile (stack, seniority, location).
4. Generates tailored cover letters and CV variants with the Claude API.
5. Exports shortlists to CSV/JSON for manual review.

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
```

### Supported job boards

| Board              | Source                                         | Notes                                                                  |
| ------------------ | ---------------------------------------------- | ---------------------------------------------------------------------- |
| `remoteworkspain`  | remoteworkspain.es                             | JSON-LD JobPosting on detail pages.                                    |
| `jobfluent`        | jobfluent.com                                  | Server-side HTML. Barcelona/EU startup jobs. 3 pages, rate-limited.    |
| `himalayas`        | himalayas.app (country=Spain)                  | Remote-first. Next.js SSR HTML. 3 pages.                               |
| `indeed_es`        | es.indeed.com                                  | Blocked by Cloudflare on direct HTTP (403). Parser ready for Playwright migration (M5). Returns empty list with warning when blocked. |

Run one board with `--board <name>` or all in parallel with `--board all`.

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

### Status

Early alpha. Not ready for production. See [roadmap](../../projects/atalaya/ai/plan.md).

### License

MIT

---

## Español

### Qué es

`atalaya-cli` es un CLI Python que:

1. Agrega ofertas dev remoto desde varios job boards españoles/EU.
2. Deduplica y almacena localmente (SQLite).
3. Puntúa cada oferta contra tu perfil (stack, seniority, ubicación).
4. Genera cartas de presentación y variantes de CV personalizadas con la API de Claude.
5. Exporta shortlists a CSV/JSON para revisión manual.

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
```

### Job boards soportados

| Board              | Fuente                                          | Notas                                                                  |
| ------------------ | ----------------------------------------------- | ---------------------------------------------------------------------- |
| `remoteworkspain`  | remoteworkspain.es                              | JSON-LD JobPosting en paginas de detalle.                              |
| `jobfluent`        | jobfluent.com                                   | HTML server-side. Startups Barcelona/EU. 3 paginas con rate limit.     |
| `himalayas`        | himalayas.app (country=Spain)                   | Remote-first. Next.js SSR. 3 paginas.                                  |
| `indeed_es`        | es.indeed.com                                   | Bloqueado por Cloudflare en HTTP directo (403). Parser listo para migrar a Playwright (M5). Devuelve lista vacia con warning cuando esta bloqueado. |

Usa `--board <nombre>` para uno solo o `--board all` para correrlos en paralelo.

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

### Estado

Alpha temprana. No listo para producción. Ver [roadmap](../../projects/atalaya/ai/plan.md).

### Licencia

MIT
