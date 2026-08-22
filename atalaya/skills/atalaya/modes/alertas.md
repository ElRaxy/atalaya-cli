# Modo alertas — leer las notificaciones por email de los portales

La vía que ningún competidor tiene, y la que mejor aguanta: aquí no hay anti-bot que
valga porque **la oferta la manda el propio portal** a tu buzón.

## Requisito previo

Hay que tener alertas creadas en LinkedIn, InfoJobs, Tecnoempleo o RemoteOK, y una
contraseña de aplicación IMAP configurada. Sin eso este modo no tiene de dónde leer, y
lo correcto es decirlo en vez de devolver cero ofertas.

## Ejecutar

```bash
bhound ingest-email --folder INBOX --since-days 7
```

Parsea los correos de alerta, extrae las ofertas y las mete en la misma base de datos
que el barrido, así que se deduplican entre sí. La idempotencia va por `Message-ID`:
volver a correrlo sobre los mismos días no duplica nada.

Después, para leerlas: `bhound export --fmt json --out /tmp/atalaya-alertas`.

## Qué esperar

Las ofertas que llegan por alerta suelen traer **menos campos** que las scrapeadas:
el correo trae título, empresa y enlace, y poco más. La descripción casi nunca viene.

No es un defecto a compensar inventando: si hace falta el detalle, el enlace lleva a
la oferta. Dilo así cuando presentes estas ofertas, para que se sepa que la ficha es
más pobre que la de un barrido.

## Cuándo usar este modo y no el barrido

Cuando el portal esté bloqueando el scraping, cuando interese solo lo que casa con una
alerta ya afinada, o cuando se quiera cobertura de portales sin scraper propio. Los dos
modos se complementan y comparten base de datos: no hay que elegir.
