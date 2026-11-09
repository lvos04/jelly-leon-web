# Patchregister jelly-leon-web (core-patches op upstream-bestanden)

Basis: `jellyfin/jellyfin-web` **v12.4** (`0a580ce8df89282dfd120b6d5efb8e106da23bd5`, zie
`tools/jelly-leon-web/baseline.json`; herbasis van P4-0, ADR-0011). Elke wijziging aan een bestand **buiten** de
fork-eigen paden (`tools/jelly-leon-web/fork_paths.txt`) ten opzichte van die basis is een **core-patch** en moet hier
staan (ADR-0001, ADR-0002). `tools/jelly-leon-web/patch_register_check.py` controleert dat in CI (job *Forkregels*):

- een niet-geregistreerd gewijzigd, toegevoegd, verwijderd of hernoemd upstream-bestand → CI faalt;
- een geregistreerd bestand dat niet (meer) afwijkt → CI faalt (register verouderd, bv. na upstream-acceptatie);
- `LICENSE` en `CONTRIBUTORS.md` mogen **nooit** afwijken (GPL-credits);
- een patch op `package.json` moet het veld **Technische identiteit** invullen: `name` blijft `jellyfin-web` en `version`
  blijft de upstream-versie (ADR-0003/ADR-0005; `check_fork_consistency.py` bewaakt dat apart).

**Volgorde vóór een core-patch** (ADR-0001): server/upstream-configuratie → bestaande upstream-plugin → eigen
serverplugin (`lvos04/jelly-leon`, `plugins/`) met een configuratiepagina → web-configuratie (`config.json`:
`menuLinks`, `plugins`) → fork-eigen code in `src/jelly-leon/` of `src/plugins/jellyLeon/` → pas dan een kleine,
geïsoleerde haak in een upstream-bestand (liefst één regel die fork-eigen code aanroept).

**Vorm per patch** (de checker leest deze tabelvelden): kop `## JLW-NNNN — titel`; `Status` ∈ `actief` |
`upstream-aangeboden` | `vervallen`; `Bestanden` met elk pad tussen backticks; verplicht ook `Doel`,
`Waarom geen plugin/configuratie`, `Upstream-PR-kans` en `Test`. Aanbevolen: `Sinds`, `B03-taak`, `Wijziging`,
`Bekend bij volgende sync`.

**Nummering** (bouwplan B03 §10.11): een JLW-nummer wordt pas toegekend als de patch echt bestaat, in volgorde. De
P0-planning noemde drie *geplande* haken "JLW-0001…0003"; die nummers zijn nooit aan een echte patch gegeven en zijn
vervallen. De haken heten nu met hun werknaam uit het bouwplan (H-ITEMDETAILS, H-ROUTE, H-PLAYBACKINFO, …) en krijgen
een nummer bij de echte patch. Daardoor is **JLW-0001** (guard) de eerste
echte patch; "opvolger van JLW-0001" in het bouwplan betekent dus H-ITEMDETAILS (zie ADR-0011 in deze repo).

## Overzicht

| ID | Titel | Soort | Status |
|---|---|---|---|
| JLW-0001 | Repository-guard op upstream-workflow `workflow_run.yml` | workflow-guard (veiligheid) | actief |

## JLW-0001 — Repository-guard op upstream-workflow `workflow_run.yml`

| Veld | Waarde |
|---|---|
| Status | actief |
| Sinds | 2026-11-09 (P4-0, herbasis op v12.4) |
| B03-taak | B03-014 (webdeel), B03-013 (upstream-sync) |
| Doel | Het in v12.0 toegevoegde upstream-bestand `.github/workflows/workflow_run.yml` geeft `JF_BOT_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` en `CLOUDFLARE_API_TOKEN` door aan herbruikbare workflows (automation, Cloudflare Pages-deploy) zonder repository-guard. In de fork mogen die jobs nooit draaien (geen deploy, geen bot, geen lege geheimen). |
| Bestanden | `.github/workflows/workflow_run.yml` |
| Wijziging | 2 regels: job `automation` krijgt `if: ${{ github.repository == 'jellyfin/jellyfin-web' }}`; de `if:` van job `deploy` wordt `github.repository == 'jellyfin/jellyfin-web' && github.event.workflow_run.conclusion == 'success'`. Job `metadata` (alleen `GITHUB_TOKEN`, alleen lezen) blijft ongewijzigd. |
| Waarom geen plugin/configuratie | Upstream-workflows staan buiten de fork-eigen paden; uitzetten via de GitHub-instellingen is onzichtbaar in de repo en wordt bij een sync niet gecontroleerd. Een guard in hetzelfde patroon als upstream zelf gebruikt (`push.yml`, `pull_request.yml`) is de kleinste zichtbare, door CI bewaakte wijziging (ADR-0007). |
| Upstream-PR-kans | Redelijk: upstream bewaakt de deploy-jobs in `push.yml` en `pull_request.yml` al met dezelfde guard; in `workflow_run.yml` ontbreekt hij. Nog niet aangeboden (R2: alleen na besluit van de gebruiker). |
| Test | `tools/jelly-leon-web/workflow_check.py` (CI-job *forkregels* én de sync-job van `upstream-sync.yml`): zonder deze patch faalt de controle met 10 onbewaakte geheimgebruiken (gemeten na de herbasis, 2026-11-09). `tests/test_workflow_check.py::test_upstream_workflow_run_v124_without_guard_fails_and_jlw_0001_fixes_it`; de guard moet een conjunct op het hoogste niveau zijn (`::test_guard_must_be_top_level_conjunct`). |
| Bekend bij volgende sync | Wijzigt upstream de `if:`-regels of jobnamen, dan geeft de herbasis een conflict (exit 2) of faalt `workflow_check.py`; guard dan op de nieuwe regels zetten. Vervalt als upstream de guard zelf toevoegt (de checker meldt dan "wijkt niet meer af"). |

## Geplande haken op de 12.x-basis (nog NIET uitgevoerd — alleen planning)

Herbeoordeeld op v12.4 (2026-11-09). De haakpunten staan met een sync-blokkerende ankercontrole in
[`UPSTREAM_GEDRAG.md`](UPSTREAM_GEDRAG.md) (webdeel, `tools/jelly-leon-web/upstream_gedrag_check.py`): verdwijnt of
verhuist een ankerpunt bij een upstream-sync, dan faalt CI vóórdat er een haak bestaat. Elke haak wordt één regel
`jlHook('naam', ctx)` naar één fork-eigen module `src/jelly-leon/hooks` (dynamische import, try/catch), bouwplan §10.11.

| Werknaam (bouwplan §10.11) | P0-planning | Upstream-bestand op v12.4 (haak) | Voor | Herbeoordeling 12.x |
|---|---|---|---|---|
| H-ITEMDETAILS | "JLW-0001" in `src/controllers/itemDetails/index.js` | `src/apps/legacy/controllers/itemDetails/index.js` (`reloadFromItem`) | B03-009 knop, F3 dialoog, F4 label | Verhuisd. Modern én Legacy laden dezelfde controller (`apps/{modern,legacy}/routes/legacyRoutes/user.ts` → `itemDetails/index`, `ViewManagerPage.tsx` importeert uit `apps/legacy/controllers/`): één haak volstaat. |
| H-ROUTE | "JLW-0002" in `src/apps/stable/routes/asyncRoutes/user.ts` of `SearchResults.tsx` | `src/apps/modern/routes/asyncRoutes/user.ts` én `src/apps/legacy/routes/asyncRoutes/user.ts` (`ASYNC_USER_ROUTES`) | B03-008 scènezoeker, F5 "Dit apparaat" | `apps/stable` heet nu `apps/legacy`, `experimental` heet `modern`; per layout een eigen routelijst, dus één routeregel per layout (of één gedeelde fork-eigen routelijst die beide lijsten aanvult). Zoekresultaten: `src/apps/legacy/features/search/components/SearchResults.tsx` (beide layouts). |
| H-PLAYBACKINFO | "JLW-0003" in `src/components/playerstats/playerstats.js` | idem, functie `getTranscodingStats` (na het blok `TranscodingInfo.TranscodeReasons`) | B03-004/005, F5 W2 | De uitgecommentarieerde regel `HardwareAccelerationType` uit 10.11 bestaat in v12.4 niet meer (gemeten); de haak komt aan het eind van de sessiestatistieken. |
| H-HOME | — | `src/components/homesections/homesections.js` (`export function loadSections`) | F2 startschermrij | Gedeeld door beide layouts. |
| H-SYNCPLAY-MENU | — | `src/apps/modern/components/AppToolbar/menus/SyncPlayMenu.tsx` | F1 W1 | Alleen Modern tenzij BG-14. |
| H-DEVICEPROFILE | — | `src/components/apphost.js` (`function getDeviceProfile`) | F5 probe/advies | Dekt browserpad en NativeShell. |
| H-SKIPTEXT | — | `src/components/playback/skipsegment.ts` (`setButtonText`) | F6 knopteksten | — |
| H-SEGACTION | — | `src/apps/legacy/features/playback/utils/mediaSegmentSettings.ts` (`DEFAULT_ACTIONS`, `getMediaSegmentAction`) | F6 Recap-standaard | Schrijft niets. |
| H-SYNCPLAY-SKIP | — | `src/apps/legacy/features/playback/utils/mediaSegmentManager.ts` (`skipSegment`) | F6/F1 groepsskip | — |

Deze werknamen krijgen pas een JLW-nummer als de haak echt bestaat; tot dan blijft het register hierboven de enige
bron van waarheid en faalt CI op elke andere afwijking.
