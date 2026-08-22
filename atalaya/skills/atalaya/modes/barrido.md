# Modo barrido — buscar ofertas hoy

## Ejecutar

```bash
bhound search --board all --limit 400
bhound export --fmt json --out /tmp/atalaya-hoy
```

El primero scrapea los nueve portales en paralelo, deduplica contra el histórico
y guarda en SQLite. El segundo vuelca lo almacenado con todos los campos: en JSON
la descripción va entera, que es lo que necesitas para juzgar.

Tarda entre 20 y 30 segundos. El cuello de botella es RemoteWorkSpain, que pide
una página de detalle por oferta.

Para un portal suelto: `--board tecnoempleo` (o `infojobs`, `jobfluent`,
`remoteworkspain`, `remoteok`, `weworkremotely`, `linkedin_public`).

## Leer el JSON

Cada oferta trae:

| Campo | Ojo con |
|---|---|
| `title`, `company`, `url` | `company` es "RemoteWorkSpain" en ese portal y no es un fallo: republica en su nombre y no expone al empleador |
| `posted_at` | `null` en InfoJobs, que no la publica en el listado. No la estimes |
| `salary_min` / `salary_max` | ausente en la gran mayoría. Normal en España |
| `description` | vacía en InfoJobs, LinkedIn y JobFluent: solo dan el titular en el listado |
| `stack` | detectado por palabras clave sobre título y etiquetas. Es una pista, no un contrato |
| `score` | pre-filtro heurístico 0-100. **No es tu criterio**: sirve para ordenar, no para descartar |

## Cómo presentarlas

Agrupa por lo que le importa a quien lee, no por portal. El portal es un detalle de
implementación; que una oferta sea de Tecnoempleo o de InfoJobs no la hace mejor.

Para cada oferta que propongas: título, empresa, **fecha**, enlace, y una línea sobre
por qué encaja o por qué no. Esa línea la escribes tú leyendo la descripción, no
copiando el `score`.

Ordena por fecha dentro de cada grupo. Una oferta de hace un mes en un mercado que se
mueve rápido probablemente esté cubierta.

Di cuántas descartaste y con qué criterio. "De las 346, 12 encajan" sin decir qué pasó
con las otras 334 es un resumen que no se puede auditar.

## Si algo sale raro

Cero ofertas de un portal que no sea Indeed ni Himalayas: correr `bhound health` antes
de sacar conclusiones. Es más probable que se haya roto el parser a que el portal se
haya quedado vacío.
