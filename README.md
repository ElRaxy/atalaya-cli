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
bhound search --remote --stack mern
bhound list --min-score 60
bhound letter <offer-id>
```

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
bhound search --remote --stack mern
bhound list --min-score 60
bhound letter <id-oferta>
```

### Estado

Alpha temprana. No listo para producción. Ver [roadmap](../../projects/atalaya/ai/plan.md).

### Licencia

MIT
