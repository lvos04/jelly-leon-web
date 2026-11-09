# Bouwverificatie P0 — jelly-leon-web

Datum 2026-11-09 · bouwomgeving: gedeelde Linux-container (4 CPU, 15 GB RAM), Node **v22.23.4**, npm **10.9.9**,
Python 3.12, Docker (daemon lokaal), Chromium 153.0.8010.12 (Playwright 1.63.0, headless) · code: upstream
v10.11.11 zonder core-patches (de broncode van de webclient is in alle onderstaande runs identiek aan upstream).
Zware stappen draaiden één voor één met `nice -n 10`. **Niets hiervan is op een NAS, tv of telefoon uitgevoerd.**

## 1. Samenvatting

> §1–§6 zijn de metingen van de bouwer; de onafhankelijke review met herhaalde metingen, gevonden
> problemen en reparaties staat in **§7** (o.a. 50 tool-tests, actionlint mét shellcheck, smoketest 30/30).

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
schermafbeeldingen `p0-web-smoke/fork-*.jpg`, `p0-upstream-syncproef-v12.4.json`). Python-venv met
`tools/jelly-leon-web/requirements-dev.txt`; `.venv/bin/python` in de tabel = die venv. Let op: zet de venv **buiten**
de repo (bv. `~/.venvs/jelly-leon-web`), want upstream-eslint lint `./` en negeert geen `.venv` in de werkmap; de
eindcontrole (§6) is daarom met een venv buiten de repo gedraaid.

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

Beide eigen workflows zijn lokaal met actionlint en `workflow_check.py` gecontroleerd.

- **`jelly-leon-web-ci.yml` is op GitHub uitgevoerd en geslaagd**: run
  [42601333719](https://github.com/lvos04/jelly-leon-web/actions/runs/42601333719) op commit `a076efb74`
  (push naar `ccr-c133d7a0-kuz1cv`, 10:30–10:37 UTC). Alle 7 jobs groen: forkregels (31 tests), eslint (0 fouten),
  stylelint, tsc, vitest 160/160, productiebuild + es-check + artefact
  `jelly-leon-web-10.11.11-jl.0-a076efb74f89.tar.gz` (Node v22.23.4, npm 10.9.9, 2317 bestanden; `npm ci` zonder
  omweg — het GitHub-archief is daar bereikbaar) en de web-client-smoketest op dat artefact **21/21**.
  Samenvatting: `test-evidence/p0-github-ci-run-42601333719.json`.
- **`upstream-sync.yml` is nog niet op GitHub uitgevoerd** (NIET GEVALIDEERD): scheduled en handmatige runs kunnen pas
  vanaf de standaardbranch.

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

## 6. Eindcontrole op de definitieve boom (na alle commits, venv buiten de repo)

| Commando | Exit | Uitkomst |
|---|---|---|
| `check_fork_consistency.py` | 0 | basis v10.11.11, forkversie 10.11.11-jl.0, identiteit jellyfin-web 10.11.11, EVIDENCE.json geldig |
| `patch_register_check.py` | 0 | 0 core-patches |
| `workflow_check.py` | 0 | 9 upstream-workflows bewaakt, 2 eigen vastgezet |
| `pytest -q -c tools/jelly-leon-web/pytest.ini tools/jelly-leon-web/tests` | 0 | 31 geslaagd |
| `actionlint -shellcheck= …` (2 eigen workflows) | 0 | geen meldingen |
| `npm run lint` | 0 | 0 fouten, 103 waarschuwingen (ongewijzigd t.o.v. §1) |
| `npm test -- --maxWorkers=2` | 0 | 12 bestanden, 160/160 |
| `npm run build:check` / `npm run stylelint` | 0 / 0 | geen fouten |

De productiebuild en de smoketest (§1, §3) zijn niet opnieuw gedraaid: de webbroncode is sindsdien niet gewijzigd
(alle latere commits raken alleen fork-eigen paden: docs, tools, workflows).

## 7. Onafhankelijke review P0 (2026-11-09, na commit `e636db6ac`)

Alles opnieuw gedraaid zoals de CI het doet, op dezelfde omgeving (venv `~/.venvs/jelly-leon-web`, Node v22.23.4,
npm 10.9.9, `nice -n 10`, één zware stap tegelijk).

| Commando | Exit | Uitkomst |
|---|---|---|
| `npm ci --no-audit --no-fund --prefer-offline` | 0 | 1724 pakketten (26 s) |
| `npm run lint` | 0 | 0 fouten, 103 upstream-waarschuwingen |
| `npm run stylelint` / `npm run build:check` | 0 / 0 | geen fouten |
| `npm test -- --maxWorkers=2` | 0 | 12 bestanden, 160/160 |
| `npm run build:production` + `npm run escheck` | 0 / 0 | webpack 5.99.9, 2 upstream-groottewaarschuwingen, 2317 bestanden; ES-versie in orde |
| `check_fork_consistency.py`, `patch_register_check.py`, `workflow_check.py --overzicht` | 0 | basis v10.11.11, 0 core-patches, 9 upstream-workflows bewaakt |
| `pytest -q -c tools/jelly-leon-web/pytest.ini tools/jelly-leon-web/tests` | 0 | **50 geslaagd** (31 bestaande + 19 nieuwe) |
| `actionlint` **met** shellcheck 0.11.0 (`shellcheck-py`) op beide eigen workflows | 0 | geen meldingen |
| `web_smoke.py --modus fork` | 0 | **30/30** (21 + herstart/terugzetten/vooruit, §7.2) |
| `web_smoke.py --modus stock` | 0 | **24/24** (21 + herstart) |
| Gepinde acties (`git ls-remote --tags`) | — | checkout v6.0.1, setup-python v6.1.0, setup-node v6.5.0, upload-/download-artifact v5.0.0: SHA's kloppen |
| `git diff --name-only 35c0793e HEAD` buiten fork-eigen paden | — | leeg: webcode, `package.json`, branding en technische identiteit ongewijzigd |
| GitHub Actions run [42610233474](https://github.com/lvos04/jelly-leon-web/actions/runs/42610233474) op `1fa0ab657` | success | 7/7 jobs; 50 tool-tests; shellcheck 0.11.0; smoketest **30/30** op de runner (`test-evidence/p0-github-ci-run-42610233474.json`) |

### 7.1 Gevonden en gerepareerd

1. **`upstream-sync.yml`, open bij fout:** `upstream_sync.py kies … | tee` draaide zonder `pipefail` (GitHub-standaard
   `bash -e`); een mislukte tagdetectie gaf dus stil "geen kandidaat". Nu `defaults.run.shell: bash`
   (`-eo pipefail`) in beide eigen workflows; getest met het echte run-script.
2. **`upstream-sync.yml`, pushtoken:** `JLW_SYNC_PUSH_TOKEN` stond in dezelfde job die upstream-code en
   `npm ci` (lifecycle-scripts van derden) uitvoert, en in de push-URL. Een kwaadaardige afhankelijkheid kon het token
   via een git-hook of `insteadOf` buitmaken. Nu: aparte job `beoordeling` op een schone runner, alleen met het
   artefact van een volledig geslaagde sync; hooks uit, token alleen via de git-config-omgeving (gemaskeerd), en een
   bestaande `sync/<tag>` wordt nooit overschreven (geen force-push). ADR-0006 punt 4.
3. **`upstream-sync.yml`, bundle:** gebruikte `github.event.repository.default_branch`, dat bij `schedule`-events
   ontbreekt; de upstream-tag zat niet in de bundle. Nu basis `GITHUB_SHA` + tag in de bundle; artefacten per tag.
4. **CI zonder shellcheck:** `actionlint -shellcheck=` zette de shell-controle uit. Nu met `shellcheck-py==0.11.0.1`
   (vastgezet in `requirements-dev.txt`).
5. **Smoketest kon "geslaagd" rapporteren zonder browserdeel:** bij ontbrekende Playwright (of mislukte serverstart)
   was alleen de exitcode 3, het JSON-rapport zei "geslaagd". Nu staat de ontbrekende stap als mislukt in het rapport.
6. **Ontbrekende test voor herstart/terugzetten (punt 6 van de review, B03-013-webdeel):** toegevoegd, zie §7.2.

Nieuwe tests: `tools/jelly-leon-web/tests/test_sync_workflow.py` (7: pipefail overal, token alleen in een job zonder
code van derden, mislukte detectie faalt, invoer-tag gevalideerd, bundle → schone runner → push zonder tokenlek of
hooks, bestaande branch niet overschreven, zonder token niets gepusht) en `test_web_smoke_unit.py` (12: redactie,
nooit geslaagd zonder stappen, dataverlies/kapotte stream/ACL-lek/verkeerde webclient worden herkend, onbereikbare
server en ontbrekende Playwright geven "mislukt").

### 7.2 Herstart en terugzetten (Sim-getest)

Na het browserdeel (alleen als het script de server zelf start; `--zonder-herstart` slaat het over):

| Fase | Wat | fork | stock |
|---|---|---|---|
| herstart | `docker restart`; juiste webclient, zelfde server-ID, beheerder logt in met hetzelfde wachtwoord, testnummer met hetzelfde ID, `GET /Audio/<id>/stream` 200 (RIFF, 88 244 bytes), kinderprofiel 0 resultaten | ✔ (3 stappen) | ✔ (3) |
| terugzetten | nieuwe container met **dezelfde** `/config`, zonder fork-mount = stock-webclient van de image (vorige binary) — zelfde controles | ✔ (3) | — |
| vooruit | weer met de fork-build — zelfde controles | ✔ (3) | — |

Dit toont voor het webdeel dat wisselen tussen fork-build en stock-webclient de gebruikers, bibliotheek, streams en
server-ACL niet raakt. Het **DB-back-up-deel** van B03-013 (terugzetten van de serverdatabase) hoort bij de server
(`lvos04/jelly-leon`) en de echte NAS: NIET GEVALIDEERD.

### 7.3 Niet gedaan / blijft open

- Geen eigen image voor deze repo (ADR-0008): "alles-in-één image bouwt, start met lege `/appdata`, herstart zonder
  dataverlies" is niet van toepassing. De **web-build binnen de jelly-leon-image** is nog niet getest: de
  jelly-leon-CI vervangt de web-stage in P0 door de upstream-dist, en de web-stage (`COPY --from=jelly-leon-web . .`,
  `npm ci` in Docker) loopt in deze bouwomgeving vast op de GitHub-archief-403 → followup voor `lvos04/jelly-leon`.
- `upstream-sync.yml` is nog steeds niet op GitHub gedraaid (alleen vanaf de standaardbranch); de run-scripts zijn
  wel lokaal in bash getest.
