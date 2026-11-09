# ADR-0004 — Platformschermen in de Hub-UI; in de webclient alleen in-context-elementen; beveiliging op de server

- **Status:** Aanvaard (P0, 2026-11-09)
- **Context:** Contract §1: "alle schermen van alle nieuwe diensten staan in die ene Hub-UI" (Next.js-PWA in
  `ai-server-manager`). B03 §1 noemt echter schermen die bij het kijken horen (Zoek en scène, Speler,
  Kwaliteitsweergave) en B03-009 vraagt een knop "bij titel". 08_UI: "playback uit Jellyfin"; de Hub deep-linkt.
  Dit is een spanningsveld: dezelfde functie kan in de Hub of in de webclient landen.

## Besluit (veiligste interpretatie)

1. **Platform- en beheerschermen** — versie & clientcompatibiliteit (B03-001), updatecentrum (B03-013), overzicht en
   goedkeuring van MediaGuard-aanvragen (B03-009, R2), problemen, instellingen van platformkoppelingen — staan
   **alleen in de Hub-UI**. Instellingen van de Jelly Leon-plugin zelf gaan via de upstream-plugin-configuratiepagina.
2. **In de webclient** komen alleen kleine **in-context-elementen** die zonder kijkcontext zinloos zijn: knop + leverstatus
   op de detailpagina, scène-resultaten met "afspelen vanaf tijdcode", kwaliteitslabel/hardware-lane in de speler.
   Ze praten uitsluitend met de eigen server (`/media/v1/*`, zelfde origin, Jellyfin-sessie).
3. **Beveiliging** (rollen, kinderprofiel-ACL, verborgen media) wordt **op de server** afgedwongen; de webclient filtert
   niet zelf als beveiligingsmaatregel en krijgt nooit Hub-, MediaGuard- of TrueNAS-geheimen.

## Gevolgen

- Geen tweede beheer-UI in de webclient; de Hub blijft één plek voor goedkeuringen en audit.
- Gemeld als contract-issue: contract §1 zegt niets expliciets over in-context-elementen in de Jellyfin-webclient.
