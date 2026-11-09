# Bouwverificatie P0 — jelly-leon-web

Datum 2026-11-09 · bouwomgeving: gedeelde Linux-container (4 CPU, 15 GB RAM), Node **v22.23.4**, npm **10.9.9**,
Python 3.12, Docker (daemon lokaal), Chromium 153.0.8010.12 (Playwright 1.63.0, headless) · code: upstream
v10.11.11 zonder core-patches (de broncode van de webclient is in alle onderstaande runs identiek aan upstream).
Zware stappen draaiden één voor één met `nice -n 10`. **Niets hiervan is op een NAS, tv of telefoon uitgevoerd.**

## 1. Samenvatting

| # | Commando (repo-root) | Exit | Uitkomst | Duur |
|---|---|---|---|---|
| 1 | `npm ci --no-audit --no-fund --prefer-offline` | 0 | 1724 pakketten; 10 upstream-`deprecated`-waarschuwingen | 36 s |
| 2 | `npm test -- --maxWorkers=2` | 0 | vitest: **12 bestanden, 160/160 geslaagd** | 5 s |
| 3 | `npm run lint` | 0 | eslint: **0 fouten**, 103 waarschuwingen (allemaal upstream) | 2 min 46 s |
| 4 | `npm run stylelint` | 0 | 0 problemen | 5 s |
| 5 | `npm run build:check` | 0 | `tsc --noEmit`: 0 fouten | 16 s |
| 6 | `npm run build:production` | 0 | webpack 5.99.9 "compiled with 2 warnings" (upstream-groottewaarschuwingen: asset > 244 KiB, entrypoint `main.jellyfin` 3,15 MiB); `dist/` 2317 bestanden, ~60 MB | 2 min 37 s |
| 7 | `npm run escheck` | 0 | "ES-Check: there were no ES version matching errors!" | 3 s |
| 8 | `.venv/bin/python tools/jelly-leon-web/check_fork_consistency.py` | 0 | basis v10.11.11 (35c0793ece3a), forkversie 10.11.11-jl.0, identiteit jellyfin-web 10.11.11 | <1 s |
| 9 | `.venv/bin/python tools/jelly-leon-web/patch_register_check.py` | 0 | 0 core-patches; alle afwijkingen in fork-eigen paden | <1 s |
| 10 | `.venv/bin/python tools/jelly-leon-web/workflow_check.py --overzicht` | 0 | 9 upstream-workflows (geheimen bewaakt), 2 eigen (vastgezet) | <1 s |
| 11 | `.venv/bin/python -m pytest -q -c tools/jelly-leon-web/pytest.ini tools/jelly-leon-web/tests` | 0 | **31 geslaagd** (incl. EX48-simulaties) | 3 s |
| 12 | `.venv/bin/actionlint -shellcheck= .github/workflows/jelly-leon-web-ci.yml .github/workflows/upstream-sync.yml` | 0 | geen meldingen (shellcheck niet beschikbaar in deze omgeving) | <1 s |
| 13 | `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python tools/jelly-leon-web/e2e/web_smoke.py --modus fork --uitvoer <map>` | 0 | **21/21 stappen geslaagd** (fork-build) | 40 s |
| 14 | idem met `--modus stock` | 0 | **21/21 stappen geslaagd** (webclient uit de officiële image, referentie) | 40 s |
| 15 | syncproef v12.4 (tijdelijke kloon; §5) | 2 / 0 / 1 | merge: 30 conflicten; herbasis: 0 conflicten maar `workflow_check` en `npm ci` falen terecht | — |

De ruwe rapporten staan in `docs/platform-v2/test-evidence/` (`p0-web-smoke/web-smoke-{fork,stock}.json`,
schermafbeeldingen `p0-web-smoke/fork-*.jpg`, `p0-upstream-syncproef-v12.4.json`). Venv: `.venv` in de repo-root
(alleen lokaal, uitgesloten via `.git/info/exclude`) met `tools/jelly-leon-web/requirements-dev.txt`.

## 2. Bijzonderheid: GitHub-archief van `classlist.js` geblokkeerd in deze bouwomgeving

`package-lock.json` haalt `classlist.js@1.2.20180112` op als `https://github.com/eligrey/classList.js/archive/1.2.20180112.tar.gz`
(integriteit `sha512-5rjszPzc…r+1yBg==`). In deze bouwomgeving geeft de uitgaande proxy daarop **HTTP 403** (ook
`codeload.github.com`). GitHub Actions heeft die toegang wel; de repo is **niet** aangepast. Lokaal opgelost, met
dezelfde integriteitscontrole als npm zelf:

```sh
git clone --bare https://github.com/eligrey/classList.js.git repo.git            # git-protocol is wel toegestaan
git -C repo.git archive --format=tar --prefix=classList.js-1.2.20180112/ 1.2.20180112 | gzip -n > classlist.tgz
openssl dgst -sha512 -binary classlist.tgz | base64 -w0                           # = integriteit uit package-lock.json
npm cache add ./classlist.tgz                                                     # inhoud in de npm-cache (op digest)
npm ci --prefer-offline                                                           # npm controleert de sha512 opnieuw
```

De zelf gemaakte tarball is **byte-gelijk** aan het GitHub-archief (sha512 gelijk aan `package-lock.json`), dus de
installatie is identiek aan die op GitHub Actions. Ook de web-stage van de jelly-leon-image liep hier op deze 403 vast
(ADR-0008 in `lvos04/jelly-leon`); daar helpt dezelfde aanpak niet zonder Dockerfile-wijziging (andere repo, followup).

## 3. Web-client-smoketest (Sim-getest)

`tools/jelly-leon-web/e2e/web_smoke.py` start `docker.io/jellyfin/jellyfin:10.11.11@sha256:aefb67e6…` als 568:568,
`--cap-drop ALL`, `no-new-privileges`, poort alleen op 127.0.0.1, met een zelfgegenereerde WAV (2 s, 440 Hz) als
alleen-lezen bibliotheek. In modus `fork` wordt `dist/` alleen-lezen op `/jellyfin/jellyfin-web` gemount; in modus
`stock` gebruikt de server zijn eigen webclient. Wachtwoorden zijn per run willekeurig en komen niet in het rapport.

| # | Stap | fork | stock |
|---|---|---|---|
| 1 | server gezond (`/health`) | ✔ | ✔ |
| 2 | technische identiteit: `ProductName` "Jellyfin Server", `Version` 10.11.11 | ✔ | ✔ |
| 3 | juiste webbron geserveerd (fork: `/web/index.html` byte-gelijk aan `dist/index.html`) | ✔ | ✔ |
| 4 | zichtbare naam in P0 ongewijzigd: `<title>Jellyfin</title>`, `manifest.json` name "Jellyfin" | ✔ | ✔ |
| 5–6 | eerste-startwizard via API, beheerder logt in | ✔ | ✔ |
| 7–8 | bibliotheek "Muziek" aangemaakt, scan vindt het testnummer | ✔ | ✔ |
| 9 | kinderprofiel zonder bibliotheektoegang (`EnableAllFolders=false`) | ✔ | ✔ |
| 10 | zoeken via API: beheerder 1 resultaat, kinderprofiel 0 (server-ACL) | ✔ | ✔ |
| 11 | zonder token geweigerd (HTTP 401) | ✔ | ✔ |
| 12 | aanmeldpagina in het Nederlands (browser `nl-NL`: "Meld je aan", "Gebruiker", "Wachtwoord", "Aanmelden") | ✔ | ✔ |
| 13 | fout wachtwoord geweigerd, melding "Ongeldige gebruikersnaam of wachtwoord" (negatieve test) | ✔ | ✔ |
| 14 | inloggen → startscherm met bibliotheek "Muziek" | ✔ | ✔ |
| 15 | zoeken in de UI vindt "Sinus 440 Hz" | ✔ | ✔ |
| 16 | detailpagina → afspelen → `GET /Audio/<id>/…` HTTP 200 | ✔ | ✔ |
| 17 | kinderprofiel: zoeken in de UI geeft "Geen resultaten gevonden", titel niet zichtbaar | ✔ | ✔ |
| 18–21 | startscherm op 360/390/768/1440 px zonder horizontale overloop | ✔ | ✔ |

Conclusie: de fork-build gedraagt zich in deze reizen gelijk aan de stock-webclient (geen regressie). **Beperking:**
headless Chromium op Linux; geen echte tv, telefoon, Chromecast, ondertitels of video-transcoding getest →
NIET GEVALIDEERD (hardware, D15).

## 4. CI op GitHub

`.github/workflows/jelly-leon-web-ci.yml` en `upstream-sync.yml` zijn lokaal met actionlint en `workflow_check.py`
gecontroleerd, maar **nog niet op GitHub uitgevoerd** (NIET GEVALIDEERD). `upstream-sync.yml` draait als scheduled
workflow pas vanaf de standaardbranch.

## 5. Syncproef naar upstream v12.4 (tijdelijke kloon, niets gepusht)

1. `upstream_sync.py kies` → spoor `patch`: geen kandidaat; spoor `nieuwste`: **v12.4** (v12.0…v12.4).
2. `merge --tag v12.4 --methode merge` → **exit 2**, 30 conflicten in bestanden die de fork nooit wijzigde
   (upstream-backports op de 10.11-releasebranch); werkboom schoon, geen branch achtergelaten.
3. `merge --tag v12.4` (auto → **herbasis**) → exit 0; `sync/v12.4` = upstream-tag + fork-eigen paden,
   merge-commit met beide ouders; baseline 12.4.0-jl.0.
4. Na de sync: consistentie en patchregister in orde; **`workflow_check.py` faalt** (nieuw upstream-bestand
   `workflow_run.yml` geeft `JF_BOT_TOKEN`/`CLOUDFLARE_*` zonder repository-guard door, 10 bevindingen) en
   **`npm ci` faalt** (`EBADENGINE`: v12.4 eist node ≥ 24.0.0, npm ≥ 11.0.0). De workflow zou dus terecht falen (EX48).
5. v12.4 bouwen/testen is niet uitgevoerd (Node 24 niet aanwezig) — NIET GEVALIDEERD.
