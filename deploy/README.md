# deploy/ — jelly-leon-web

Deze repo heeft **geen** eigen image, Custom App of manifest (ADR-0008): de webclient zit in `ghcr.io/lvos04/jelly-leon`.

| Bestand | Inhoud |
|---|---|
| `truenas/CUSTOM_APP.md` | waarom er geen eigen formulier is en waar het `jelly-leon`-formulier staat |

Ontwikkelen: `npm ci && npm start` (webpack-devserver; vraagt in de browser om een serveradres). Testen tegen een echte
server zonder eigen installatie: `tools/jelly-leon-web/e2e/web_smoke.py` (start de officiële serverimage, op digest
vastgezet, alleen lokaal op 127.0.0.1). Compose wordt in deze repo niet gebruikt.
