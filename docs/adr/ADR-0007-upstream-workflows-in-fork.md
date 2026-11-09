# ADR-0007 — Upstream-workflows ongewijzigd; guards bewaakt door `workflow_check.py`

- **Status:** Aanvaard (P0, 2026-11-09); aangevuld in P4-0 met guard-patch JLW-0001 (ADR-0011)
- **Context:** Door het samenvoegen van de upstream-historie staan de workflows van jellyfin-web in de fork. Opdracht:
  upstream-workflows niet stilletjes uitzetten; documenteren en repository-guards toevoegen waar ze upstream-geheimen
  nodig hebben. Upstream-geheimen: `JF_BOT_TOKEN` (bot-commentaar, labels, stale), `CLOUDFLARE_API_TOKEN`/
  `CLOUDFLARE_ACCOUNT_ID` (Cloudflare Pages-deploy).

## Meting (v10.11.11, `workflow_check.py --overzicht`)

| Workflow | Trigger | Geheimen | Guard in de fork |
|---|---|---|---|
| `push.yml` | push `master`, `release*` | via `__automation`/`__deploy` | jobs `automation`/`deploy` hebben al `github.repository == 'jellyfin/jellyfin-web'` |
| `pull_request.yml` | PR naar `master`, `release*`; merge_group | via `__job_messages`/`__automation`/`__deploy` | `push-comment`, `automation`, `deploy`, `run-eslint` al bewaakt |
| `schedule.yml` | dagelijks, handmatig | `JF_BOT_TOKEN` | al bewaakt: `contains(github.repository, 'jellyfin/')` |
| `__quality_checks.yml` | aanroep, handmatig | geen | n.v.t. (bij een handmatige run in de fork verwijst dependency-review naar `master`, die hier niet bestaat → zou falen; niet gemeten, geen geheim) |
| `__automation.yml`, `__deploy.yml`, `__job_messages.yml`, `__codeql.yml`, `__package.yml` | alleen `workflow_call` | zie boven | via de (bewaakte) aanroepers |

## Besluit

- **Geen enkele upstream-workflow gewijzigd of uitgeschakeld** in P0: alle geheimgebruik zit al achter een
  repository-guard, dus een guard-patch zou alleen sync-conflicten opleveren.
- `tools/jelly-leon-web/workflow_check.py` controleert dit bij elke CI-run én na elke upstream-sync, ook transitief via
  herbruikbare workflows met `secrets: inherit` of expliciet doorgegeven geheimen. Komt er een onbewaakt gebruik bij,
  dan faalt CI en wordt een guard toegevoegd als geregistreerde patch (`JLW-NNNN`, net als JL-0001 in de server).
- Fork-branches zijn zo gekozen dat upstream-triggers niet afgaan: `main`, `ccr-**`, `sync/**`, `release/**`
  (`release*` in upstream matcht geen `/`).
- Eigen workflows: `jelly-leon-web-ci.yml` en `upstream-sync.yml` (acties op commit-SHA, `permissions: contents: read`).
- `.github/renovate.json` en `.github/CODEOWNERS` ongewijzigd (zonder Renovate-app/upstream-team geen effect).

## Gevolgen

- Bekend voor 12.x: upstream v12.4 voegt `workflow_run.yml` toe dat `JF_BOT_TOKEN` en `CLOUDFLARE_*` zonder guard
  doorgeeft (gemeten, 10 bevindingen) → guard-patch nodig vóór overname (ADR-0006).
- `jelly-leon-web-ci.yml` draaide op GitHub (run 42601333719, geslaagd) zonder dat een upstream-workflow afging op de
  fork-branch `ccr-c133d7a0-kuz1cv` (alleen "Jelly Leon Web CI" verscheen). `upstream-sync.yml`: NIET GEVALIDEERD.

## Aanvulling P4-0 (2026-11-09, ADR-0011)

v12.4 brengt `workflow_run.yml` mee, dat upstream-geheimen zonder guard doorgeeft. Zoals hierboven voorzien is de guard
toegevoegd als geregistreerde patch **JLW-0001**. `workflow_check.py` telt een guard sindsdien alleen als conjunct op
het hoogste niveau van de `if:` (`guard && …`); `guard || …` geldt als onbewaakt.
