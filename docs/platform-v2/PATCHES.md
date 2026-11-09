# Patchregister jelly-leon-web (core-patches op upstream-bestanden)

Basis: `jellyfin/jellyfin-web` **v10.11.11** (`35c0793ece3adbd247eab290ae1effab851f3d37`, zie
`tools/jelly-leon-web/baseline.json`). Elke wijziging aan een bestand **buiten** de fork-eigen paden
(`tools/jelly-leon-web/fork_paths.txt`) ten opzichte van die basis is een **core-patch** en moet hier staan
(ADR-0001, ADR-0002). `tools/jelly-leon-web/patch_register_check.py` controleert dat in CI (job *Forkregels*):

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

## Overzicht

| ID | Titel | Soort | Status |
|---|---|---|---|
| — | (geen) | — | — |

**Stand P0 (2026-11-09): geen enkele core-patch.** De broncode van de webclient is identiek aan upstream v10.11.11;
alle fork-eigen bestanden staan in fork-eigen paden (docs, tools, eigen workflows). Ook de upstream-workflows zijn
ongewijzigd: alle upstream-geheimen (`JF_BOT_TOKEN`, `CLOUDFLARE_*`) zitten in v10.11.11 al achter een
repository-guard (gemeten met `workflow_check.py`, ADR-0007), dus een guard-patch is niet nodig.

## Verwachte patches in latere fasen (nog NIET uitgevoerd — alleen planning, zie FORK_STRATEGIE.md §4)

| Gepland | B03-taak | Upstream-bestand (haak) | Fork-eigen code | Waarom vermoedelijk een haak nodig is |
|---|---|---|---|---|
| JLW-0001 | B03-009 MediaGuard-verzoeklink | `src/controllers/itemDetails/index.js` (één aanroep) | `src/jelly-leon/mediaguard/` | detailpagina heeft geen uitbreidingspunt voor een knop per titel |
| JLW-0002 | B03-008 scènezoeker | `src/apps/stable/routes/asyncRoutes/user.ts` (één route) of `SearchResults.tsx` (één sectie) | `src/jelly-leon/scenes/` | upstream-routes en zoekresultaten zijn een vaste lijst |
| JLW-0003 | B03-004/005 kwaliteitsweergave | `src/components/playerstats/playerstats.js` (één categorie) | `src/jelly-leon/quality/` | upstream toont *Playback Info* al; alleen het kwaliteitslabel ontbreekt |

Deze ID's worden pas toegekend als de patch echt bestaat; tot dan blijft het register leeg en faalt CI op elke
afwijking.
