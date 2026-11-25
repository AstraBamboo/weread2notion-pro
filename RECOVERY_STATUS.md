# Recovery candidate — not deployed or accepted

Prepared 2026-11-23 for AstraBamboo/weread2notion-pro, based on 49f8107.

## Implemented locally

- Both schedules: Sunday UTC 05:00 and 15:00 (Asia/Shanghai 13:00, 23:00).
- Install this checkout instead of the unrelated released PyPI package.
- Guard both reading-duration writers: finite numeric values strictly greater than 500, in original seconds. Preserve disqualified historical rows.
- Use Notion API 2025-09-03 data sources; reject ambiguous multi-source destinations.
- Stop automatic schema changes, database creation, credential copying to Notion, and deletion of existing notes/chapters.
- Paginate Notion child blocks and WeRead notebooks/reviews; verify duration writes by reading the page back.
- Use WeRead API Key gateway for shelf, notebooks, bookmarks, reviews, chapters and daily statistics.
- Read-only preflight before each workflow; serialize workflows and do not cancel an active writer.
- Remove old heatmap generation/publishing step, which depends on the obsolete cookie package; preserve existing Notion heatmap embed and repository images.

## Unresolved acceptance gates

- GitHub Actions remains disabled; no usable historical run logs were returned.
- GitHub Secrets had NOTION_TOKEN, NOTION_PAGE, WEREAD_COOKIE and NAME, but no WEREAD_API_KEY at inspection.
- Gateway documentation exposes cumulative per-book progress, not equivalent per-book daily reading detail. The original readinfo endpoint remains isolated for this capability and fails explicitly when unavailable. No cumulative totals are fabricated into daily book records.
- Existing Cookie is dated March 2025; validity is unknown. NOTION_TOKEN/NOTION_PAGE validity has not been tested by Actions.
- No real sync or writeback has occurred. Do not describe this candidate as restored.

## Validation

`python -m unittest discover -s tests -v`: 13 tests passed using mocked APIs.
Syntax compilation and `git diff --check` passed. These are not online acceptance.

Before merging: validate secrets, run both read-only preflights against the target, resolve per-book daily detail availability, run full workflows, inspect logs, independently verify existing Notion schema/content and written records, then repeat to check idempotency.
