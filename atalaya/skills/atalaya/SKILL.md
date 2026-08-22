---
name: atalaya
version: 0.1.0
description: |
  Busca ofertas de trabajo dev en los portales españoles que las herramientas
  internacionales no cubren (InfoJobs, Tecnoempleo, JobFluent, RemoteWorkSpain)
  y en los remote-first grandes, y te las entrega como hechos para que TU las
  juzgues. Incluye ingesta de las alertas por email de los propios portales,
  que esquiva el anti-bot porque la oferta la manda el board.
  Usar cuando alguien pida buscar empleo dev en España, revisar ofertas nuevas,
  ver el estado de sus candidaturas, o mencione InfoJobs, Tecnoempleo o
  "ofertas remoto España".
allowed-tools:
  - Bash
  - Read
  - Write
---

# Atalaya

Atalaya no puntúa ofertas por ti: te trae los hechos y **el juicio lo pones tú**.

Esa división es deliberada. El CLI extrae de cada portal el título, la empresa, la
fecha, el stack, el salario cuando lo hay y la descripción. Lo que no hace nunca es
emitir un "esta oferta te encaja": eso es un juicio, y un juicio agregado por un
programa tapa los datos que lo contradicen.

## Qué cubre esto que no cubre otra cosa

`career-ops` y `JobSpy` resuelven muy bien el mercado internacional y **no tocan
ni un portal español**. Atalaya existe por ese hueco:

| Portal | Qué aporta |
|---|---|
| Tecnoempleo | el grueso del mercado dev español |
| InfoJobs | el portal generalista de referencia en España |
| JobFluent | ofertas tech en inglés, foco Barcelona y Madrid |
| RemoteWorkSpain | remoto con contrato español |

Y además los remote-first grandes: We Work Remotely, RemoteOK y la búsqueda pública
de LinkedIn.

**Para el CV a medida y la carta de presentación, usa `career-ops`.** Lo hace mejor
y no tiene sentido competirle. Atalaya termina donde empieza esa parte: su trabajo
es que tengas delante las ofertas correctas.

## Antes de nada

Comprueba que el binario responde:

```bash
bhound version
```

Si no responde, ojo: **el paquete todavia no esta publicado en PyPI** y
`pip install atalaya-cli` falla con un 404. Hoy se instala desde el repositorio:

```bash
git clone https://github.com/ElRaxy/atalaya-cli && cd atalaya-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
bhound init                # crea el perfil y la base de datos
```

El perfil vive en `~/Library/Application Support/atalaya/profile.toml` en macOS.
Antes del primer barrido, ábrelo y ajústalo: sin perfil el pre-filtro deja pasar
casi todo, que es lo correcto pero te da más ruido que leer.

## Los tres modos

Lee el fichero del modo cuando vayas a ejecutarlo, no antes.

| Situación | Modo |
|---|---|
| "búscame ofertas", "a ver qué hay hoy" | `modes/barrido.md` |
| "mira mis alertas de LinkedIn/InfoJobs" | `modes/alertas.md` |
| "¿cómo van mis candidaturas?" | `modes/pipeline.md` |

## La regla que no se salta

Cuando presentes ofertas, **cita siempre la URL y la fecha** de cada una. Una oferta
de hace cinco semanas y una de ayer se leen igual en un resumen, y no valen lo mismo.
Si `posted_at` viene vacío, dilo: no lo estimes por el orden del listado.

Y no inventes lo que el portal no da. El salario falta en la mayoría de ofertas
españolas: eso es un hecho sobre el mercado, no un hueco que rellenar.

## Antes de fiarte de un barrido vacío

Un scraper puede devolver cero porque el portal no tiene nada hoy, o porque se ha
roto. No son lo mismo y se distinguen con un comando:

```bash
bhound health
```

Reporta por portal cuántas ofertas devuelve, cuánto tarda y si falló. Dos dan cero
de forma permanente y es sabido: **Indeed España** (muro de Cloudflare) y
**Himalayas** (403 que no cede ni con user agent de navegador). Si alguno de los
otros siete aparece en cero, hay algo roto y lo que toca es decirlo, no barrer otra
vez con otro filtro.
