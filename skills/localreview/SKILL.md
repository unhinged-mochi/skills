---
name: localreview
description: Runs a local multi-agent bug hunt modeled on Claude Code's cloud ultrareview ("bughunter") — parallel hunters, adversarial 2-of-3 voting, root-cause synthesis, cloud-shaped findings.json — without spending ultrareview quota. Reviews the current branch against its base, a given base ref, a GitHub PR, or a whole snapshot with no common history. Use when the user types /localreview or asks for a local ultrareview / deep multi-agent review.
argument-hint: "[PR#|#PR|PR-URL|<base-ref>] [--fix] [--no-quality] [--resume] [--no-slice] [--no-cache] [free-text note]"
disable-model-invocation: true
---

# localreview

**Never** run `claude ultrareview`, `/ultrareview` or `/code-review ultra`, and never invoke the `code-review` skill: they spend paid cloud quota or follow a different recipe. Copy this rule into every subagent prompt.

Files in this skill (paths relative to its base directory, written `<skill>/` in commands):
- [reference/angles.md](reference/angles.md): hunter angles A–E, the quality hunter, the sweep. Read before Phase 1.
- [reference/formats.md](reference/formats.md): candidate, vote and finding JSON; `pr_comment`/`reasoning` conventions; the presentation template. Read before Phase 1.
- [reference/provenance.md](reference/provenance.md): what was verified about the cloud original, and how this skill scored against it. Background only; not needed to run a review.
- `templates/HUNTER_BRIEF.md`, `templates/VOTER_BRIEF.md`: shared briefs to fill in and copy to `scope/`.
- `scripts/pool.py`, `scripts/tally.py`, `scripts/synth.py`: run these (don't reimplement them). Work dir defaults to `/tmp/localreview_work`; override with `LOCALREVIEW_WORK`.
- `evals/evals.json`: scenarios to re-check after editing this skill.

Copy this checklist into your reply and tick it off:
```
localreview progress:
- [ ] 0 Parse args, build scope, print banner
- [ ] 1 Write briefs, spawn all hunters in one message
- [ ] 2 As each hunter lands: pool → 2 votes → tie-breaker; sweep after the last hunter
- [ ] 3 tally.py → synth overrides → synth.py → validate output
- [ ] 4 Present
- [ ] 5 --fix only: apply, run checks, never commit
```

## Arguments (`$ARGUMENTS`)
1. Strip the flags wherever they appear: `--fix`, `--no-quality`, `--resume`, `--no-slice`, `--no-cache`.
2. First remaining token:
   - `^\d+$`, `^#\d+$` or a `github.com/.../pull/N` URL → **PR mode**.
   - else, if `git rev-parse --verify --quiet "origin/$tok"` or `"$tok"` succeeds → **base ref**.
   - else → start of the **note**.
3. Everything left is the **note**: a priority hint for hunters and for presentation. Never abort on unknown words; show it in the banner as `Note (not a base): "…"`.

## Phase 0 — Scope
Work dir `$W` = `${LOCALREVIEW_WORK:-/tmp/localreview_work}` with `scope/ hunters/ reports/`. Wipe it unless `--resume` is set and `scope/diff.sha256` matches.

1. **Diff**
   - PR mode: `gh pr diff "$N"` and `gh pr view "$N" --json title,body,author,files`.
   - Branch mode: base = the given ref, else the default branch (`git symbolic-ref refs/remotes/origin/HEAD`, then `gh repo view --json defaultBranchRef`, then the first existing of `main master trunk develop`). `git fetch origin "$BASE" --quiet` (warn on failure), then `MB=$(git merge-base HEAD "origin/$BASE" || git merge-base HEAD "$BASE")`.
     - With MB: `git diff -U30 "$MB"` (working tree, so uncommitted tracked changes are in scope).
     - No MB: all files, `git diff -U30 4b825dc642cb6eb9a060e54bf8d69288fbee4904` (the empty tree). Banner: `Reviewing all files (no common history with $BASE)`.
   - Untracked files: warn `N untracked files aren't in scope until git tracks them (git add).`
2. Drop paths matching `.localreview-ignore` (gitignore globs); log them to `scope/ignored.txt`.
3. Empty diff → stop: `Nothing to review against $BASE. Pass a base commit (/localreview <sha>) or a PR number.`
4. Write `scope/diff.patch`, `diff.sha256`, `stat.txt`, `files.txt`, and `meta.json` = `{git_sha, base, merge_base|null, pr_number, note, flags, lang_mix, diff_lines, timestamp}` (`diff_lines` = insertions + deletions).
5. Cache: unless `--no-cache`, a matching hash with an existing `findings.json` → re-present it marked `[cache hit]` and stop.
6. Slicing: a diff over 200 KB (unless `--no-slice`) gives each hunter its file slice plus the full file list; angle C always gets the full list.
7. Banner: `Localreview launched for <branch → base | PR #N | all files>. Scope: <files> files, +I/-D. Hunters: <n>. Quality pass: on|off.`
8. From here, print `<stage> — N found, N verified, N refuted` whenever a counter changes (stages `finding`, `verifying`, `synthesizing`; counters = pooled candidates, positive votes, refuting votes).

## Phase 1 — Find (`finding`)
- Fleet: `C = clamp(ceil(diff_lines / 150), 2, 8)` correctness hunters (one hunter covers ~150 changed lines in its 10-minute budget), plus `Q = 1` quality hunter (2 above 2,000 lines) unless `--no-quality`.
- Fill in `templates/HUNTER_BRIEF.md` and `templates/VOTER_BRIEF.md` (`{{REPO}}`, `{{STACK}}` one line, `{{MODE}}`, `{{NOTE}}`, `{{RULES}}` from CLAUDE.md/AGENTS.md, `{{W}}`, `{{SKILL}}` = this skill's base directory) and write them to `$W/scope/`. Each subagent prompt is then just: "Read `$W/scope/HUNTER_BRIEF.md`. You are H<n>. Your angles: … Your slice: …".
- Assign angles from [reference/angles.md](reference/angles.md) round-robin so every angle A–E has an owner.
- Spawn **all hunters in one message** (parallel `Agent` calls, `general-purpose`). They run in the background and notify on completion, which is what lets Phase 2 pipeline.
- Resume: skip a hunter whose `hunters/H<n>/` already holds `bug_*.json`.

## Phase 2 — Verify, pipelined (`verifying`)
As each hunter's notification arrives (don't wait for all):
1. `python3 <skill>/scripts/pool.py show H<n>` prints its candidates (and flags bad JSON).
2. **Dedup**: a duplicate has the same file, lines within 10, **and** the same mechanism. `pool.py dup bug_NNN H<n>_<s>` folds it in (keep the more concrete `failure_scenario` as canonical). Different bugs in one function stay separate.
3. **Gate**: `pool.py drop <id> <reason>` for a `pr_comment` under 120 chars or no failure scenario.
4. **Cap**: 25 correctness candidates (most severe first: `normal` > `pre_existing` > `nit`, then corroboration) plus a reserve of 5 cleanup candidates. Cleanup (reuse, simplification, efficiency, altitude, conventions) waits until every hunter has returned, otherwise early cleanup eats the verify budget. Near the cap, hold `nit`s until all hunters return so the cap ranks by severity, not arrival.
5. `pool.py add H<n>_<s> …` assigns `bug_NNN`. Dispatch **2 independent voters** per new bug (≤8 `Agent` calls per message): "Read `$W/scope/VOTER_BRIEF.md` and `$W/reports/bug_NNN_candidate.json`. You are voter v."
6. **Tally** (`python3 <skill>/scripts/tally.py`; it lists bugs needing a 3rd voter): both refute → refuted; both positive → verified; split or an errored vote → dispatch a 3rd voter. Final rule: ≥2 refutes → refuted; ≥2 valid and <2 refutes → verified; otherwise unverified (reported separately, never dropped). A missing or unparseable vote is errored, never a refute.
7. **Sweep**: after the last hunter returns, spawn one fresh hunter with the verified list and the sweep angle from angles.md. Its candidates go through steps 1–6.
- Resume: votes already on disk are skipped.
- Budget: 10 min per agent. At ~30 min total, stop dispatching, mark undecided bugs unverified, and synthesize.

## Phase 3 — Synthesize (`synthesizing`)
1. Write `scope/synth_overrides.json` with this run's judgment calls (format in [reference/formats.md](reference/formats.md)):
   - `merge`: verified bugs sharing one root cause (same missing check, same fix) → secondary folds into the most severe as `[also at: …]`.
   - `canon`: when a duplicate hunter's text sits at the **root** location (where the one fix goes), use it.
   - `pr_comment`: rewrite claims the voters narrowed (e.g. "route X isn't reachable").
   - `severity`: demote to `nit` when low-frequency, abuse-only, author-acknowledged (e.g. a `ponytail:` comment), or cleanup. Otherwise leave the script's mechanical severity (voter majority, tie → hunter hint).
2. Run `python3 <skill>/scripts/synth.py`. It writes `findings.json` (headline: every `normal` and `pre_existing`, at most 8 `nit`s), `findings.more.json` (other verified nits), `findings.meta.json`, `unverified.json`, `findings.sarif`, and prints any shape errors.
3. **Fix every error synth.py prints and re-run it** before presenting.
4. PR mode: mark findings within ±10 lines of an existing PR review comment `already_discussed` in the sidecar and fold them under `<details>`.

## Phase 4 — Present
Use the template in [reference/formats.md](reference/formats.md#presentation). Open with one line tying findings to the note if there was one. Warn when refuted votes exceed 90% of all votes (noisy hunters or harsh voters) or verified votes exceed 95% with more than 5 found (rubber-stamping).

## Phase 5 — `--fix`
Apply findings to the working tree, most severe first, using each `sweep:` regex to reach every occurrence. Skip, with a one-line reason, any fix that changes intended behavior, reaches well outside the scope, or that you now judge a false positive. Run the project's checks (typecheck, lint, tests). **Never commit, stage or push.** End with `Fixed: … · Skipped: … · Checks: pass|fail (<tail>)`.
