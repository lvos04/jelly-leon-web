# TrueNAS Home Platform V2 — documentatie voor `jelly-leon-web`

Bron: uitvoeringspakket `TrueNAS_Home_Platform_V2_VOLLEDIG_2026-11-09.zip` (peildatum 9 november 2026).

**Rol van deze repo (vast besluit):** Fork van jellyfin/jellyfin-web v10.11.11.

Hier staan alleen de eigen B-, I-, A- en promptdocumenten plus de gedeelde architectuur (`00_START`, `01_ARCHITECTUUR`, `05_TESTS`). Het volledige pakket en de Excel staan in `lvos04/ai-server-manager` onder `docs/platform-v2/`.

Onbekende NAS-gegevens (D01–D18) worden nooit met voorbeeldwaarden ingevuld; ze worden via de onboarding-wizard in de web-UI vastgelegd.

## Platformcontract 1.2

- [`PLATFORM_CONTRACTEN.md`](PLATFORM_CONTRACTEN.md) (`contracts 1.2`) en
  [`CONTRACT_1.2_CONFORMITEIT.md`](CONTRACT_1.2_CONFORMITEIT.md) zijn **byte-gelijke kopieën** uit
  `lvos04/ai-server-manager` (bron van waarheid) op bron-commit `8b54f39`. Nooit hier bewerken: een nieuwe stand
  overnemen = opnieuw byte-gelijk kopiëren en bron-commit + sha256 in `tools/jelly-leon-web/contract_drift.py`
  bijwerken. De drifttest (`contract_drift.py`, tests in `tools/jelly-leon-web/tests/test_contract_drift.py`) draait in
  de CI-job *forkregels* online tegen de bron.
- Relatieve links in de kopieën (bv. `../adr/ADR-0011-contract-1-2.md`) wijzen naar bestanden in
  `ai-server-manager`, niet naar de ADR's van deze repo.
- Wat 1.2 voor deze repo betekent (JW1–JW3, A1–A7): [`docs/adr/ADR-0010-contract-1-2.md`](../adr/ADR-0010-contract-1-2.md).

## Bestanden

- `PLATFORM_CONTRACTEN.md` (kopie, `contracts 1.2`)
- `CONTRACT_1.2_CONFORMITEIT.md` (kopie)
- `00_START/BESLUITEN_EN_ONBEKENDEN.md`
- `00_START/INHOUDSOPGAVE.md`
- `00_START/INHOUD_CONTROLE.json`
- `00_START/LEES_MIJ_EERST.md`
- `00_START/SHA256SUMS.txt`
- `01_ARCHITECTUUR/01_PROJECTCHARTER.md`
- `01_ARCHITECTUUR/02_DATA_EIGENAARSCHAP.md`
- `01_ARCHITECTUUR/03_RISICO_AUTONOMIE.md`
- `01_ARCHITECTUUR/04_GEGEVENS_EN_STORAGE.md`
- `01_ARCHITECTUUR/05_OPERATIES_EN_UPDATES.md`
- `01_ARCHITECTUUR/06_FASERING_EN_GATES.md`
- `01_ARCHITECTUUR/07_API_EN_EVENTSCHEMA.md`
- `01_ARCHITECTUUR/08_UI_EN_INTERACTIES.md`
- `02_BOUWPLANNEN/B03_UNIVERSELE_MEDIASERVER.md`
- `03_INSTALLATIE/I06_JELLYFIN.md`
- `03_INSTALLATIE/I24_UNIVERSELE_MEDIASERVER.md`
- `04_BESTAANDE_APPS/A17_JELLYFIN.md`
- `05_TESTS/GEBRUIKERSWENSEN_TRACEERBAARHEID.md`
- `05_TESTS/INTEGRALE_E2E_TESTMATRIX.md`
- `06_TEMPLATES/PROMPTS_PER_APP/PROMPT_B03_UNIVERSELE_MEDIASERVER.md`
