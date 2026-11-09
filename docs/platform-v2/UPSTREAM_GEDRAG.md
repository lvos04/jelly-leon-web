# Register van upstream-gedrag — webdeel (jelly-leon-web)

Bouwplan B03 §10.11 en B03-019 (a): elk upstream-gedrag waarop de webfork steunt zonder dat het een vaste API is, staat
hier met een **sync-blokkerende test**. Het serverdeel (`UG-F1…F6-<n>`, contracttests op `JL_RUNTIME_IMAGE`) staat in
`lvos04/jelly-leon` → `docs/platform-v2/UPSTREAM_GEDRAG.md`. Het webdeel heeft een eigen reeks **`UG-WEB-<n>`**, zodat
de nummers nooit botsen met die van het serverregister; de functie (F1…F6 of gemeenschappelijk) staat in een kolom.

**Test per regel.** `tools/jelly-leon-web/upstream_gedrag_check.py` zoekt per regel het *anker* (Python-regex, meerdere
regels toegestaan) in het genoemde upstream-bestand van de huidige boom. Verdwijnt of verhuist een anker bij een
upstream-sync, dan faalt de controle — in de CI-job *forkregels* én in de sync-job van `upstream-sync.yml` — en wordt
de sync niet overgenomen (EX48, JLT-67). Een `UG-WEB-<n>`-verwijzing in de documentatie zonder regel hier laat de
controle ook falen. Het gedrag zelf in een browser (layouts, identiteit, legacy-authenticatie) bewaakt de
web-client-smoketest (`tools/jelly-leon-web/e2e/web_smoke.py`).

Basis: `jellyfin/jellyfin-web` v12.4 (`0a580ce8df89`). Nog geen enkele haak is gebouwd (P4-0); de regels leggen de
haakpunten van [`PATCHES.md`](PATCHES.md) ("Geplande haken op de 12.x-basis") en het gedrag van de smoketest vast.

| ID | Haak / gedrag | Bestand | Anker | Gebruikt door | Test |
|---|---|---|---|---|---|
| UG-WEB-1 | H-ITEMDETAILS: detailpagina wordt opgebouwd in `reloadFromItem` | `src/apps/legacy/controllers/itemDetails/index.js` | `function reloadFromItem\(instance, page, params, item, user\)` | B03-009, F3 (W2), F4 (W4) | anker |
| UG-WEB-2 | H-ITEMDETAILS: Modern laadt de detailpagina met de legacy-controller | `src/apps/modern/routes/legacyRoutes/user.ts` | `path: 'details',\s*pageProps: \{\s*controller: 'itemDetails/index'` | B03-009, F3, F4 | anker |
| UG-WEB-3 | H-ITEMDETAILS: legacy-controllers komen voor beide layouts uit `apps/legacy/controllers/` | `src/components/viewManager/ViewManagerPage.tsx` | `apps/legacy/controllers/\$\{controller\}` | B03-009, F3, F4 | anker |
| UG-WEB-4 | H-ROUTE: eigen gebruikersroutes in Modern | `src/apps/modern/routes/asyncRoutes/user.ts` | `export const ASYNC_USER_ROUTES: AsyncRoute\[\] = \[` | B03-008, F5 (W4) | anker |
| UG-WEB-5 | H-ROUTE: eigen gebruikersroutes in Legacy | `src/apps/legacy/routes/asyncRoutes/user.ts` | `export const ASYNC_USER_ROUTES: AsyncRoute\[\] = \[` | B03-008, F5 (W4) | anker |
| UG-WEB-6 | H-PLAYBACKINFO: transcodeerstatistieken met redenen | `src/components/playerstats/playerstats.js` | `function getTranscodingStats\(session, player, displayPlayMethod\)[\s\S]*?TranscodingInfo\.TranscodeReasons` | B03-004/005, F5 (W2) | anker |
| UG-WEB-7 | H-HOME: startschermsecties (`loadSections`, gedeeld door beide layouts) | `src/components/homesections/homesections.js` | `export function loadSections\(elem, apiClient, user, userSettings\)` | F2 (W-1) | anker |
| UG-WEB-8 | H-SYNCPLAY-MENU: SyncPlay-menu in de Modern-werkbalk | `src/apps/modern/components/AppToolbar/menus/SyncPlayMenu.tsx` | `const SyncPlayMenu: FC<SyncPlayMenuProps>` | F1 (W1) | anker |
| UG-WEB-9 | SyncPlay-instance: één `Manager` per webclient | `src/plugins/syncPlay/core/index.js` | `const Manager = new ManagerClass\(PlayerFactory\);` | F1 | anker |
| UG-WEB-10 | H-DEVICEPROFILE: afspeelprofiel van de browser en NativeShell | `src/components/apphost.js` | `function getDeviceProfile\(item\)` | F5 (probe/advies) | anker |
| UG-WEB-11 | H-SKIPTEXT: knoptekst van de skipknop | `src/components/playback/skipsegment.ts` | `setButtonText\(\) \{` | F6 (H1) | anker |
| UG-WEB-12 | H-SEGACTION: standaardactie per segmenttype | `src/apps/legacy/features/playback/utils/mediaSegmentSettings.ts` | `const DEFAULT_ACTIONS: Partial<Record<MediaSegmentType, MediaSegmentAction>>[\s\S]*?export function getMediaSegmentAction\(` | F6 (H2) | anker |
| UG-WEB-13 | H-SYNCPLAY-SKIP: overslaan in het afspeelpad | `src/apps/legacy/features/playback/utils/mediaSegmentManager.ts` | `skipSegment\(mediaSegment: MediaSegmentDto\)` | F6 (H3), F1 | anker |
| UG-WEB-14 | Webplugins via `config.json` (`plugins`, gelezen door `getPlugins`) | `src/scripts/settings/webSettings.js` | `export function getPlugins\(\)` | F1, F5, F6 (webplugins), config.json-generator | anker |
| UG-WEB-15 | Standaardlayout is Modern (12.x) | `src/components/apphost.js` | `function getDefaultLayout\(\) \{\s*return LayoutMode\.Modern;` | smoketest (beide layouts), alle webhaken | anker + smoketest `[Modern] layout actief` |
| UG-WEB-16 | Layoutinstelling `layout` in localStorage; `desktop-legacy` kiest de Legacy-app | `src/constants/layoutMode.ts` | `DesktopLegacy = 'desktop-legacy'` | smoketest (Legacy) | anker + smoketest `[Legacy] layout actief` |
| UG-WEB-17 | idem: sleutel van de instelling | `src/components/layoutManager.js` | `export const SETTING_KEY = 'layout';` | smoketest (Legacy) | anker |
| UG-WEB-18 | Technische identiteit: clientnaam richting server "Jellyfin Web" | `src/components/apphost.js` | `const appName = 'Jellyfin Web';` | ADR-0003, JLW-0002 | anker + smoketest `technische identiteit webclient` |
| UG-WEB-19 | Zichtbare titel wordt de servernaam zodra die bekend is (12.x); "Jelly Leon" is de terugval | `src/scripts/libraryMenu.js` | `documentTitle = ServerName \x7c\x7c documentTitle;` | JLW-0002 | anker |

Regels voor dit register:

- Elke nieuwe webhaak (PATCHES.md) en elk upstream-gedrag waarop fork-eigen webcode steunt, krijgt hier eerst een
  regel; het nummer volgt de reeks en wordt nooit hergebruikt.
- Het anker is zo specifiek als nodig (functiesignatuur, niet alleen een naam), zodat een stille wijziging van de
  aanroep opvalt. `|` in een regex schrijf je als `\x7c` (tabelscheiding).
- Een gefaalde regel na een upstream-sync betekent: eerst het gedrag opnieuw beoordelen (en zo nodig de haak
  verplaatsen), dan pas het anker aanpassen — nooit alleen het anker "groen maken".
