# Provenance

Background on what this skill copies and how well it matched. Not needed to run a review.

## Contents
- The cloud original (observed)
- Measured against the cloud
- Deliberate differences

## The cloud original (observed)
Observed from Claude Code 2.1.x behavior and a live `claude ultrareview --json` run (71 files, ~7k diff lines, 7.5 min), 2026-10.
- **Budget**: fleet of 5 (cap 20), 10 min per agent, 600 s agent timeout, 22 min wall-clock. Code-quality pass on by default. Refuses before launch above 500 files / 8,000 diff lines.
- **Scope**: `merge-base..HEAD`; untracked files excluded with a "run git add" warning; no merge-base → all files against the empty tree; PR mode reviews `refs/pull/N/head`.
- **Stages**: `finding` → `verifying` → `synthesizing`, pipelined. The observed run showed 20 found, 18 verified, 10 refuted, 10 final findings; since 18 + 10 > 20 the counters most likely count verdicts (inferred).
- **Output**: exactly `file_path, severity, start_line, end_line, pr_comment, reasoning`; severities `normal 🔴`, `nit 🟡`, `pre_existing 🟣`. Text conventions are in formats.md.
- **Severity in practice**: `normal` for realistic correctness/auth/billing/data-integrity bugs; `nit` for low-frequency, abuse-only, author-acknowledged and quality-pass findings.
- **`--fix`**: the local model applies findings to the working tree, skips wrong or unworthy ones, and runs checks. A free-text note never reaches the cloud.
- **Verify lineage**: 3 votes per item, ≥2 refutes kill, an errored vote is unverified.
- The cloud's hunter and verifier prompts are server-side and were not captured.

## Measured against the cloud
Same snapshot, one local run:
- The cloud reported 10 findings. One was a **false positive**: it assumed an auth plugin option let anonymous sessions through, but the installed library version refused them. The cloud trusted its idea of the library; nobody read the installed source.
- Local recall on the 9 real findings: **9/9, severity agreement 9/9**. Upper bound: hunters and voters were blind, but the orchestrator had seen the cloud output.
- Local also verified 18 findings the cloud didn't report.
- Cost: 10 hunters + 1 sweep + 64 votes, 15.4 min, vs the cloud's 7.5 min.
- Lesson baked into angle D and the voter brief: claims about library behavior are settled by the installed source, in both directions.

## Deliberate differences
- 2 votes + a tie-breaker instead of 3 votes (same outcome under the 2-of-3 rule, fewer agents).
- Angles come from Claude Code's local `/code-review` max recipe, the closest shipped sibling.
- Report bar (all normals + ≤8 nits headline): local voters keep far more than the cloud reports (27 of 30 vs 10 of 20 in the comparison), with the same severities on shared findings.
- The note is also handed to hunters as a priority hint.
