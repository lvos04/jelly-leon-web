# ADR-0012 — Platformcontract 1.3 in jelly-leon-web (kopie, drifttest-pin, bewijsregels §11)

- **Status:** Aanvaard (contractronde 1.3, 2026-11-10). Vult ADR-0010 (contract 1.2) aan; wat daar staat blijft
  gelden waar 1.3 het niet vervangt.
- **Context:** `lvos04/ai-server-manager` heeft `contracts 1.3` vastgesteld (`PLATFORM_CONTRACTEN.md` met de
  review-correcties RV1–RV13; motivering `ai-server-manager:docs/adr/ADR-0027-contract-1-3.md` en
  `ai-server-manager:docs/adr/ADR-0028-review-contract-1-3.md`) en per repo opgeschreven wat er moet veranderen
  (`CONTRACT_1.3_CONFORMITEIT.md`). Voor deze repo (hoofdstuk 10) zijn dat twee NU-punten: **C1.3-JLW-01** (kopie 1.3 +
  drifttest-pin) en **C1.3-JLW-02** (EVIDENCE-consistentie), naast de punten voor alle repos (C1.3-ALG-01…05) en het
  repowerk C07. De conformiteitslijst noemt als al conform: de drifttest zelf, GPL-2.0 (upstream) en "§10 geldt niet
  voor de webclient". Gelezen stand van deze repo in die lijst: `5ced8a246`.

## Besluit

1. **C1.3-JLW-01 / C1.3-ALG-01 — kopieën en drifttest-pin.**
   `docs/platform-v2/PLATFORM_CONTRACTEN.md` (`contracts 1.3`) en `docs/platform-v2/CONTRACT_1.3_CONFORMITEIT.md` zijn
   byte-gelijk overgenomen uit `ai-server-manager` op bron-commit **`02b119cb84be`** ("Contract 1.3: MediaGuard-overstap
   naar de publieke repo gemeten (RV13)"): de laatste commit die een van de bestanden wijzigde; op de kop van de
   bronbranch (`c63b32e`, 2026-11-10) zijn ze gelijk. `CONTRACT_1.2_CONFORMITEIT.md` mag als historie blijven staan;
   omdat de bron die lijst na `8b54f39` nog heeft aangevuld, is ook die kopie opnieuw byte-gelijk genomen op dezelfde
   bron-commit en mee vastgezet. Een kopie die niet vastgezet is, kan stil afwijken; dat willen we bij geen enkele kopie.
   `tools/jelly-leon-web/contract_drift.py` controleert nu:
   - offline (altijd): sha256 van alle drie gelijk aan de pin; de versiekop `contracts 1.3` in het contract; de kop
     `# Conformiteit met contract 1.3` van de lijst; contract én 1.3-lijst staan in de pinlijst (alleen het contract
     vastzetten is geen drifttest van beide);
   - in CI (job *forkregels*): `--online --github` tegen `raw.githubusercontent.com` op de bron-commit, met een
     `::warning::` als de bronbranch daarna verder is gegaan (overnemen = stap van de orkestratie);
   - lokaal: `--bron-map ../ai-server-manager` (leest alleen, `git show`).
   De tests in `tools/jelly-leon-web/tests/test_contract_drift.py` hebben een tweede, vaste plek voor bron-commit en
   sha256: wie de pin stil verandert zonder de kopieën opnieuw te nemen, laat de test falen. 1.3 verwijst naar bestanden
   in `ai-server-manager` als tekst (`ai-server-manager:<pad>`), niet meer als relatieve link: het punt "kapotte
   relatieve links" uit ADR-0010 (gevolgen, punt 2) is daarmee vervallen.
2. **C1.3-JLW-02 / C1.3-ALG-02 — EVIDENCE volgens §11 van 1.3.** `tools/jelly-leon-web/check_fork_consistency.py`
   (CI-stap *forkregels*) bewaakte al: alleen lijstwaarden, nooit `Gereed`/`Geslaagd`, fail-closed bij een ontbrekend of
   leeg bestand en "elke `NIET GEVALIDEERD (…)` uit `blokkade` ook in `validatie`" (review 1.2, commit `b20c7e1a9`).
   Erbij in 1.3, telkens in de veiligste lezing:
   - `Intel-iGPU-getest (ontwikkelmachine)` is een lijstwaarde, maar **alleen samen met** `NIET GEVALIDEERD (hardware)`:
     §11 zegt dat het niets over de GPU's van de NAS zegt en dat die niet gevalideerd blijven.
   - `Niet getest` is een lijstwaarde, **alleen bij status `Niet gestart`** (§11), **nooit naast een testuitkomst**
     (`Sim-getest`, `Unit-getest`, `Sim-geslaagd`, `Sim-mislukt`, iGPU); omgekeerd draagt een rij `Niet gestart` geen
     testuitkomst (dan is er getest en is de status `Bezig` of `Geblokkeerd`). `NIET GEVALIDEERD (…)` mag ernaast.
   - Een `NIET GEVALIDEERD (…)` in `blokkade` moet een **waarde uit de vaste lijst** zijn (een samengestelde reden zoals
     `(echte NAS/hardware)` kan nooit in `validatie` staan en faalt nu met een eigen melding); een lege `validatie` (ook
     alleen spaties) blijft een fout.
   - **Contractpunten en reviews** mogen een eigen regel hebben (§11, K9): `C1.3-<code>` en `C1.2-<code>` alleen als de
     code echt in de gekopieerde lijst staat, onder "voor alle repos" of "jelly-leon-web" (punten van andere repos horen
     niet in het bewijs van deze repo; ontbreekt de lijst, dan fail-closed); reviews als
     `REVIEW-jelly-leon-web-<onderwerp>`. Zij volgen de statussen van het blad Werkpakketten en krijgen geen
     testmatrixwaarde.
   - Testrijen (`EX..`, `JLT-..`) houden `Sim-geslaagd`/`Sim-mislukt`; een deels uitgevoerde testrij mag `Sim-getest`
     dragen (zoals de referentietest `ai-server-manager:apps/api/tests/unit/test_evidence_contract.py`).
   Alle bestaande regels voldeden al; `EVIDENCE.json` kreeg de regels C1.3-JLW-01 en C1.3-JLW-02 (status `Bezig`,
   `Unit-getest`: code + tests + CI, geen NAS nodig; nooit `Gereed`).
3. **C1.3-ALG-03 — licentie:** GPL-2.0-or-later van upstream blijft (conform, niets gewijzigd).
4. **Niet van toepassing in deze repo** (geen nieuwe dienst, geen eigen image, ADR-0008; contract §10 laatste zin):
   C1.3-ALG-04 (healthcheck/rooktest van een eigen image: dat doet de `jelly-leon`-image, C1.3-JL-03), de
   gemeenschappelijke punten voor de vijf eigen diensten (adressen, koppelbestand, statuspagina, JWT, sleutels, API,
   connector, events, manifest) en C1.3-ALG-05 (Peil): §13 zegt "Niet: Jelly Leon (web en clients) houdt de
   Jellyfin-vormgeving met alleen de zichtbare naam". De algemene kwaliteitseis "alles-in-één image, `CUSTOM_APP.md`,
   manifest en OpenAPI per repo" past hier niet; C1.3-ASM-23 legt vast dat die tekst niet meer aan deze repo wordt
   opgelegd. `deploy/truenas/CUSTOM_APP.md` blijft uitleggen waarom er geen eigen Custom App is.
5. **Repowerk C07.** De Node-image op digest in `tools/jelly-leon-web/baseline.json` → `toolchain` blijft een
   repo-keuze (ADR-0011). De haaknamen in deze repo zijn al de werknamen van het bouwplan (H-ITEMDETAILS, …; `PATCHES.md`,
   `UPSTREAM_GEDRAG.md`). Gemeten op 2026-11-10: het bouwplan in `ai-server-manager` noemt nog
   "H-ITEMDETAILS (opvolger JLW-0001)"; zolang dat zo is, blijft de byte-gelijke kopie hier ook zo (niets lokaal
   aanpassen).
6. **Besluiten van de gebruiker na 1.3.** De kopie `docs/platform-v2/02_BOUWPLANNEN/B03_BESLUITEN.md` is opnieuw
   byte-gelijk genomen uit `ai-server-manager@c63b32e` (noodlogin alleen vanaf het LAN, app-ID's van de clients
   bevestigd, BG-04: de MediaGuard-sleutel van Jelly Leon loopt via de Hub, extra's). Voor de webclient verandert er nu
   niets: de webclient krijgt nooit een MediaGuard-sleutel (beveiliging op de server, ADR-0004); BG-04 hoort bij de
   Hub-koppeling van de plugin in `lvos04/jelly-leon` (C1.3-JL-06/-08).

## Gevolgen

- De job *forkregels* faalt als een kopie afwijkt of de pin niet klopt; een nieuwere bronstand geeft alleen een
  waarschuwing. Wordt `ai-server-manager` ooit privé, dan faalt de online-stap terecht met exit 3 (zie ADR-0010).
- **Aanvulling uit de onafhankelijke review (2026-11-11, commits `53a5dd99e` en `de963856d`):**
  1. De zin hierboven over exit 3 klopte nog niet. Gemeten: GitHub antwoordt met 404 op elk bestand als de repo of de
     commit daar niet te lezen is, en de drifttest meldde dat als drift (exit 1), alsof de kopieën gewijzigd waren. Nu
     geldt: is op de bron-commit geen enkel vastgezet bestand te vinden, dan is dat een omgevingsfout (exit 3);
     ontbreekt een deel, dan blijft dat drift (exit 1). Hetzelfde voor een `--bron-map` zonder de bron-commit. Wat de
     sha256-pin offline al vaststelde, blijft ook bij exit 3 zichtbaar. Nooit "in orde".
  2. De regel "elke `NIET GEVALIDEERD (…)` uit `blokkade` staat ook in `validatie`" zocht alleen de exacte
     schrijfwijze. Een bijna-goede vorm (kleine letters, zonder spatie of haakjes, een regeleinde ertussen) gaf nul
     meldingen en ontliep zo de vergelijking. Zo'n vorm is nu zelf een fout; gewone lopende tekst ("is nog niet
     gevalideerd op GitHub") blijft toegestaan. Dit is strenger dan §11 letterlijk vraagt (veiligste lezing).
  Bewijs: [`c13-review-qa.json`](../platform-v2/test-evidence/c13-review/c13-review-qa.json).
- Het bewijs is strenger: een regel met `Niet getest` en een testuitkomst, een iGPU-bewijs zonder hardwarevoorbehoud,
  een zelfbedachte `NIET GEVALIDEERD`-reden of een contractpunt van een andere repo laat de CI falen.
- Gemelde contractpunten (veiligste lezing gekozen, ook als contract_issue gemeld):
  1. C1.3-ALG-01 zegt dat `CONTRACT_1.2_CONFORMITEIT.md` "als historie mag blijven staan", maar niet of die kopie dan
     byte-gelijk aan de (sindsdien gewijzigde) bron moet zijn. Gekozen: byte-gelijk op dezelfde bron-commit en vastgezet.
  2. §11 zegt "`Niet getest` alleen bij status `Niet gestart`", maar niets over combinaties. Gekozen: nooit naast een
     testuitkomst, en een rij `Niet gestart` draagt geen testuitkomst.
  3. §11 zegt bij `Intel-iGPU-getest (ontwikkelmachine)` dat de GPU's van de NAS `NIET GEVALIDEERD (hardware)` blijven,
     maar niet dat die waarde in dezelfde regel moet staan. Gekozen: verplicht ernaast.
  4. §11 zegt niet of een repo contractpunten van andere repos in zijn eigen bewijs mag zetten. Gekozen: alleen de
     punten voor alle repos en die voor deze repo, en alleen als ze in de gekopieerde lijst staan.
  5. De algemene werkopdracht van deze ronde noemt nog de kwaliteitseis "alles-in-één image, CUSTOM_APP.md, manifest,
     OpenAPI" voor elke repo; voor deze repo geldt C1.3-ASM-23 / contract §10 laatste zin (niet van toepassing).
- Niets hiervan is op een echte NAS getest; de punten zijn documentatie- en CI-regels (`Unit-getest`).
