# Formats

## Contents
- Candidate (hunter output)
- Vote (voter output)
- Synth overrides
- Finding (cloud shape) and its text conventions
- Sidecar and SARIF
- Presentation

## Candidate
One file per candidate: `$W/hunters/H<n>/bug_<seq>.json`. Hunters return only the written paths plus `hit cap | under cap`.
```json
{
  "id": "H<n>_<seq>",
  "category": "correctness|security|billing|data-integrity|concurrency|error-handling|reuse|simplification|efficiency|altitude|conventions|<slug>",
  "severity_hint": "normal|nit|pre_existing",
  "file_path": "<repo-relative>", "start_line": 0, "end_line": 0,
  "pr_comment": "<one paragraph, 150-600 chars>",
  "reasoning": "<trigger → mechanism with file:line → impact → 'A correct fix …'>",
  "failure_scenario": "<concrete inputs/state → wrong result (cleanup: the concrete cost)>",
  "pattern": "<regex matching every occurrence if the issue repeats, else null>",
  "related_files": []
}
```
`severity_hint`: `normal` = introduced or exposed bug with a realistic trigger; `nit` = rare/narrow, acknowledged trade-off, or cleanup; `pre_existing` = real bug in touched code the change didn't introduce (never in all-files mode).

## Vote
`$W/reports/<bug_id>_vote<v>.json`:
```json
{"verdict":"CONFIRMED|PLAUSIBLE|REFUTED","severity":"normal|nit","qualifier":"low frequency | acknowledged in code | cleanup | ''","trigger":"<one line>","how":["<file:line — step>"],"evidence":"<strongest argument, quoting lines>","caught_by_existing_test":null}
```

## Synth overrides
`$W/scope/synth_overrides.json`; every key optional:
```json
{
  "canon":     {"bug_001": "H3_2"},
  "merge":     {"bug_003": "bug_013"},
  "pr_comment":{"bug_018": "<narrowed text>"},
  "severity":  {"bug_022": "nit"},
  "also_at":   {"bug_002": [["src/x.tsx", 883, "<that site's comment>"]]}
}
```
`merge` maps secondary → primary. `canon` maps a bug to the duplicate candidate whose text to use.

## Finding
`findings.json` / `findings.more.json`: an array of objects with **exactly** these six keys, sorted normal → pre_existing → nit, then path, then line:
`file_path, severity (normal|nit|pre_existing), start_line, end_line, pr_comment, reasoning`.

`pr_comment` is one paragraph with no newlines:
- Conditional bug: `Condition: <precondition>. Under that condition, <failure>.`
- Merged sibling: `… [also at: <path>:<line> - <that site's comment>]`
- Repeated pattern: ends with ``sweep:`<regex>` ``

Example:
> Condition: a free user (limit 1 project) deletes their only project to start over. Under that condition projectBlocked sees owned=0, deleted=1 and `(counts.deleted ?? 0) >= limits.projects` is 1 >= 1, so createProject refuses the new project until the soft-deleted one is purged.

`reasoning` = the hunter narrative, then `\n\n**Verification:** <severity>[ (<qualifier>)]. Trigger: <trigger>. <evidence>`, then `How it happens:` with the voters' `file:line` steps. If a vote refuted, append `### Addressing the refutation` with that evidence.

## Sidecar and SARIF
- `findings.meta.json`: per finding `{bug_id, category, votes: "2-0|2-1|3-0", source_ids, corroborated_by, merged_sites}`.
- `unverified.json`: bug ids with no decision.
- `findings.sarif`: SARIF 2.1.0, `ruleId = bug_id`; `normal`/`pre_existing` → `warning`, `nit` → `note`.

## Presentation
```
Review complete — <N> findings   (<found> found, <verified> verified, <refuted> refuted[, <u> unverified])

🔴 path/to/file.ts:12-18
<pr_comment>

🟣 …   (pre_existing)
🟡 …   (nit)

<k> more verified nits in findings.more.json
Unverified: <one line each>
Files: findings.json · findings.meta.json · findings.sarif
Agents: <h> hunters + 1 sweep, <v> votes. Wall-clock: <s>s.
```
