# ADR-0005 — Versieschema: `package.json` blijft upstream, forkversie in `baseline.json`

- **Status:** Aanvaard (P0, 2026-11-09)
- **Context:** Serverfork: forkversie `<upstream>-jl.<N>` (nu `10.11.11-jl.0`, nooit gepubliceerd; eerste release
  `-jl.1`), server blijft de upstream-versie melden (`lvos04/jelly-leon` ADR-0005). De webclient bouwt de versie uit
  `package.json` in de bundel en toont die in het dashboard ("Over").

## Besluit

- `package.json` `version` blijft de **upstream-versie** (nu 10.11.11) — technische identiteit (ADR-0003).
- Forkversie in `tools/jelly-leon-web/baseline.json` → `fork_version` = `<upstream>-jl.<N>`, nu `10.11.11-jl.0`;
  gelijk aan de server bij een gezamenlijke release. Git-tags: `v<forkversie>` (eigen), `upstream-v<tag>` (lokaal).
- Het CI-artefact heet `jelly-leon-web-<forkversie>-<commit12>.tar.gz` met `bouwinfo.json` (forkversie, upstream-tag,
  commit, Node/npm); `JELLYFIN_VERSION` = commit-SHA als bouwlabel.
- `check_fork_consistency.py` bewaakt: forkversie hoort bij de basis, basis zit in de historie, `package.json`/
  `package-lock.json` = `jellyfin-web` + upstream-versie.

## Gevolgen

- Geen eigen versienummer zichtbaar in de webclient in P0; de Hub toont de forkversie via `GET /media/v1/version`
  (serverplugin). `baseline.json` hoort gelijk te lopen met `web_upstream_tag`/`web_upstream_commit` in de server-
  baseline (nu beide v10.11.11 / `35c0793ec`); een automatische kruiscontrole tussen de repo's is een followup.
