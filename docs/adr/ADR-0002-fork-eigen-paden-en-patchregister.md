# ADR-0002 — Fork-eigen paden en patchregister met CI-controle

- **Status:** Aanvaard (P0, 2026-11-09)
- **Context:** GPL-2.0 §2a (wijzigingen herkenbaar), B03-013 (patch stack minimaal en bewaakt), dezelfde regel als de
  serverfork (`lvos04/jelly-leon` ADR-0001/0002). Zonder automatische controle sluipen stille wijzigingen in
  upstream-bestanden de fork in en maken elke sync duur.

## Besluit

- Bron van waarheid voor de basis: `tools/jelly-leon-web/baseline.json` (`upstream_tag`, `upstream_commit`,
  `fork_version`, `package_name`).
- Fork-eigen paden: `tools/jelly-leon-web/fork_paths.txt` — nu `README.jelly-leon.md`, `.env.example`,
  `docs/platform-v2/`, `docs/adr/`, `deploy/`, `tools/jelly-leon-web/`, de twee eigen workflows en (gereserveerd)
  `src/jelly-leon/` en `src/plugins/jellyLeon/`.
- Alles daarbuiten dat afwijkt van `upstream_commit` is een core-patch en moet in `docs/platform-v2/PATCHES.md`
  staan (velden Status, Doel, Bestanden, Waarom geen plugin/configuratie, Upstream-PR-kans, Test; bij `package.json`
  ook Technische identiteit). `LICENSE` en `CONTRIBUTORS.md` mogen nooit afwijken.
- `tools/jelly-leon-web/patch_register_check.py` controleert dit in CI (job *Forkregels*) en faalt ook op een verouderd
  register (geregistreerd bestand wijkt niet meer af).
- Lokale Python-artefacten worden genegeerd via `tools/jelly-leon-web/.gitignore` (fork-eigen), zodat de upstream-
  `.gitignore` ongewijzigd blijft.

## Gevolgen

- De herbasis-methode van de upstream-sync (ADR-0006) gebruikt precies dit register: nieuwe basis = upstream-tag +
  fork-eigen paden + geregistreerde patches.
- Nieuwe webcode in de gereserveerde mappen wordt door upstream-eslint/tsc/vitest meegecontroleerd (zelfde regels).
