# Modo pipeline — en qué estado están las candidaturas

## Ejecutar

```bash
bhound list --limit 40
bhound list --status applied
bhound export --fmt csv --out ~/candidaturas
```

`list` muestra lo almacenado ordenado por score con su estado. El CSV es para mirarlo
en una hoja de cálculo: ahí la descripción va recortada a 300 caracteres a propósito,
porque ese formato se lee con ojos.

## Los estados

Una oferta pasa de no tener candidatura a tenerla cuando se aplica con `bhound apply`
o se registra un apply manual con `bhound apply-manual`.

Al informar del pipeline, separa siempre **ofertas vistas** de **candidaturas
enviadas**. Son dos números y confundirlos infla el trabajo hecho.

## Lo que esto NO hace

No hay seguimiento de respuestas: nadie lee el buzón para marcar quién ha contestado y
quién no. Si preguntan "¿me han respondido?", la respuesta honesta es que Atalaya no lo
sabe y hay que mirar el correo.

Tampoco aplica solo. `bhound apply` manda un email cuando la oferta publica una
dirección, y `apply-manual` prepara el material para que la persona rellene el
formulario. **Nada se envía sin que alguien lo mire antes**, y esa es una decisión de
diseño, no una carencia: un formulario relleno por un bot con datos aproximados
quema la candidatura y la empresa.
