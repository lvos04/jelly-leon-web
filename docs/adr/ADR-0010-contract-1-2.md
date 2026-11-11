# ADR-0010 — Platformcontract 1.2 in jelly-leon-web (kopie, drifttest, bewijsregels, JW1–JW3)

- **Status:** Aanvaard (contractronde 1.2, 2026-11-09)
- **Context:** `lvos04/ai-server-manager` heeft `contracts 1.2` vastgesteld (`PLATFORM_CONTRACTEN.md`, met de
  review-correcties R1–R12) en per repo opgeschreven wat er moet veranderen (`CONTRACT_1.2_CONFORMITEIT.md`, §0 A1–A7
  voor alle repos, §10 JW1–JW3 voor deze repo). Deze repo is een fork van `jellyfin/jellyfin-web` v10.11.11 zonder
  core-patches, zonder eigen image (ADR-0008) en zonder eigen API. Ook vóór deze ronde was de CI groen
  (run 42610233474).

## Besluit

1. **A1 — kopie en drifttest.** `docs/platform-v2/PLATFORM_CONTRACTEN.md` en `docs/platform-v2/CONTRACT_1.2_CONFORMITEIT.md`
   zijn byte-gelijk overgenomen uit `ai-server-manager` op bron-commit `8b54f39408e2` (sha256 vastgezet in
   `tools/jelly-leon-web/contract_drift.py`). De drifttest controleert:
   - altijd (offline): sha256 van beide kopieën gelijk aan de pin, en de kop `contracts 1.2` aanwezig;
   - in CI (job *forkregels*): `contract_drift.py --online --github` — kopie byte-gelijk aan de bron op de bron-commit
     via `raw.githubusercontent.com` (publieke repo, geen token, 4 pogingen). Is de bron daarna gewijzigd, dan alleen
     een waarschuwing: een nieuwe contractstand overnemen is een stap van de orkestratie (contract A1), niet iets wat
     deze repo zelf beslist;
   - lokaal met `--bron-map ../ai-server-manager` (vergelijkt met `git show`; leest alleen).
   Een onbereikbare bron is een omgevingsfout (exit 3) en nooit "in orde". Dezelfde opzet als
   `tools/jelly-leon/contract_drift.py` in de serverfork, zodat beide Jellyfin-forks één werkwijze hebben.
   De kopieën worden hier nooit bewerkt; hun relatieve links (`../adr/ADR-0011-…`, `../adr/ADR-0012-…`) verwijzen naar
   `ai-server-manager` en werken in deze repo niet (byte-gelijkheid gaat voor).
2. **A2 — attributie.** Commits eindigen met de attributieregel van de lopende sessie; geen sessielink (§12).
3. **A3 — scan van de historie.** De repo staat op 2026-11-09 al **publiek** op GitHub (gemeten met
   `gh repo view`); de scan is dus een controle achteraf, alleen gelezen en gemeld, niets herschreven (geen
   force-push). Doorzocht: de fork-eigen commits (`245239f61`, `3363f135e`, `94d2fd06e` en `6fde14bf6..HEAD` zonder
   de upstream-merge) op privé-LAN-adressen, thuismappen, sleutels/tokens en e-mailadressen. Bevindingen voor de
   gebruiker: geen echte geheimen, LAN-adressen of thuismappen; wel een **nep-token** met GitHub-voorvoegsel en
   PAT-lengte in `tools/jelly-leon-web/tests/test_sync_workflow.py` (de nepwaarde met tokenvorm, testwaarde voor de
   redactiecontrole), dat geheimscanners kunnen melden; verder alleen `example.invalid`/`noreply`-adressen. De
   upstream-historie van jellyfin-web is van zichzelf publiek.
4. **A4 — EVIDENCE.json streng volgens §11.** `check_fork_consistency.py` (CI-stap *forkregels*) eist nu: precies de
   velden van §11; `validatie` alleen waarden uit de vaste lijst, meerdere gescheiden door `"; "`, geen dubbele en
   geen vrije tekst (die hoort in `opmerking`); `Sim-geslaagd`/`Sim-mislukt` alleen voor de testmatrix (EX..);
   `Gereed`/`Geslaagd` nooit; niet-leeg `bewijs`; en elke commit die in `bewijs` staat bestaat echt in deze repo
   (verwijzingen naar andere repos schrijf je als `<repo>@<sha>`). Tot nu toe was elke tekst die met een geldige waarde
   begon (en zelfs alleen `NIET GEVALIDEERD`) toegestaan.
   **Aanvulling uit de onafhankelijke review (2026-11-09, commit `b20c7e1a9`):** de controle was *fail-open* — een
   ontbrekend `EVIDENCE.json` gaf "in orde". Nu is een ontbrekend bestand of een lege lijst een overtreding; elke
   `NIET GEVALIDEERD (…)` die in `blokkade` staat, moet ook als lijstwaarde in `validatie` staan (anders leest de
   Excel-kolom als volledig Sim-getest terwijl de blokkade iets anders zegt); `bijgewerkt` moet een echte
   kalenderdatum zijn. Daarbij zijn B03-001 (`echte NAS` erbij), I24-24-01 (`hardware` erbij) en I06-06-07
   (`echte NAS` erbij) rechtgezet: hun blokkade/opdracht noemde al een echte NAS of echte apparaten.
5. **A5–A7 en A6 — niet van toepassing.** Deze repo is geen nieuwe dienst: geen enrollment, geen dienst-JWT, geen
   `hub-link.json` (§2.3 regel 2: Jellyfin/Jelly Leon heeft in v1 geen enrollment). Er is geen eigen image (ADR-0008),
   dus ook geen eigen rooktest op `Uid 568`/`CapEff 0`/`NoNewPrivs 1`; dat doet de jelly-leon-image
   (`exec setpriv`, conformiteitslijst §9). Geen eigen API, dus geen OpenAPI-export: de webclient gebruikt de
   ongewijzigde Jellyfin-API, waarvan de export in `lvos04/jelly-leon` staat.
6. **JW1 — niet in deze ronde.** De upgrade naar de nieuwste stabiele 12.x (besluit 2) is een eigen fase vóór P4,
   samen met de server. De basis blijft v10.11.11. Al bekend uit de syncproef van P0 (`BOUWVERIFICATIE_P0.md` §5):
   v12.4 eist Node ≥ 24/npm ≥ 11, en het nieuwe upstream-bestand `workflow_run.yml` heeft een repository-guard nodig.
7. **JW2 — alleen de zichtbare naam.** "Jelly Leon" blijft de enige merkwijziging (ADR-0003); die is nog niet
   doorgevoerd (0 core-patches, titel en `manifest.json` nog "Jellyfin", gecontroleerd door de smoketest). De
   ontwerptaal Peil (§13: Tailwind 4 + shadcn/ui + lucide) is **niet** van toepassing op de webclient: er komt geen
   Tailwind/shadcn in deze repo en de Jellyfin-vormgeving blijft.
8. **JW3 — opnieuw geprobeerd wat in de oude sandbox geblokkeerd was.** Op de eigen bouwmachine van de gebruiker met
   direct internet: `npm ci` met een **lege** npm-cache haalt `classlist.js` rechtstreeks van GitHub
   (`codeload.github.com`, HTTP 200; sha512 gelijk aan `package-lock.json`). De omweg uit `BOUWVERIFICATIE_P0.md` §2
   is daar niet meer nodig en blijft alleen beschreven voor bouwomgevingen achter een proxy. Daarna de volledige build
   en alle tests lokaal (resultaten: `BOUWVERIFICATIE_P0.md` §8, `test-evidence/c12-jw3-lokale-bouw.json`).

## Gevolgen

- De CI hangt in de job *forkregels* af van `raw.githubusercontent.com`. Wordt `ai-server-manager` privé, dan faalt die
  stap terecht (exit 3) en moet de online-controle een leestoken krijgen of naar `--bron-map` in een aparte checkout.
- Een nieuwe contractstand bij de bron geeft in CI een `::warning::`, geen rode build; overnemen blijft een bewuste stap.
- Strengere bewijsregels: een `bewijs` met een niet-bestaande commit of vrije tekst in `validatie` laat de CI falen.
- Gemelde contractpunten (veiligste lezing gekozen):
  1. A1 zegt "niet per repo zelf aanpassen", de orkestratie vraagt deze repo de kopie te maken: gedaan als
     byte-gelijke kopie zonder enige aanpassing, met drifttest — de repo beslist niets over de inhoud.
  2. De byte-gelijke kopie bevat relatieve links naar ADR's van `ai-server-manager`; die werken hier niet. Niet
     "gerepareerd" (dan is de kopie niet meer byte-gelijk); uitgelegd in `docs/platform-v2/README.md`.
  3. De algemene kwaliteitseis "alles-in-één image, CUSTOM_APP.md, manifest, OpenAPI per repo" past niet op een
     webclient die in de jelly-leon-image zit (§2.3: één app `jelly-leon`); blijft ADR-0008 en punt 5 hierboven.
