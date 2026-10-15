# Hunter angles

## Contents
- Assigning angles
- A–E correctness angles
- Quality hunter
- Sweep

## Assigning angles
Round-robin so every angle has an owner. Below five correctness hunters, combine: C=2 → {A,B,D} + {C,E}; C=3 → {A,D}, {B,E}, {C}. A–E are Claude Code's local `/code-review` max recipe; the last sentences of C and D are additions from the comparison run.

## A — line-by-line diff scan
Read every hunk in the diff, line by line. Then Read the enclosing function for each hunk; bugs in unchanged lines of a touched function are in scope (the PR re-exposes or fails to fix them). For every line ask: what input, state, timing, or platform makes this line wrong? Look for inverted/wrong conditions, off-by-one, null/undefined deref, missing `await`, falsy-zero checks, wrong-variable copy-paste, error swallowed in catch, unescaped regex metachars.

## B — removed-behavior auditor
For every line the diff DELETES or replaces, name the invariant or behavior it enforced, then search the new code for where that invariant is re-established. If you can't find it, that's a candidate: a removed guard, a dropped error path, a narrowed validation, a deleted test that was covering a real case. In all-files mode: invariants a comment or doc *claims* that the code doesn't enforce.

## C — cross-file tracer
For each function the diff changes, find its callers (Grep for the symbol) and check whether the change breaks any call site: a new precondition, a changed return shape, a new exception, a timing/ordering dependency. Also check callees: does a parallel change in the same PR make a call unsafe? Also check that schema/migrations match queries, event emits match handlers, and webhooks/jobs tolerate retries and out-of-order delivery.

## D — language-pitfall specialist
Scan for the classic pitfalls of the diff's language/framework — for example: JS falsy-zero, `==` coercion, closure-captured loop var; Python mutable default args, late-binding closures; Go nil-map write, range-var capture; SQL injection; timezone/DST drift; float equality. Flag any instance the diff introduces. Cover the whole stack in `lang_mix` (e.g. React hooks/hydration, Workers/Durable Objects, SQL).

**Library semantics**: when a bug — or a comment's safety claim — depends on what a library, plugin option or hook does (e.g. "`authenticatedUsersOnly` keeps guests out"), read the **installed** source (`node_modules/<pkg>/dist`, `site-packages`, vendored code) at the version in the lockfile and quote the line. Don't trust the comment, the docs, or your memory of the library. This cuts both ways: it finds a guard that isn't there, and it kills a claimed hole the library already closes.

## E — wrapper/proxy correctness
When the PR adds or modifies a type that wraps another (cache, proxy, decorator, adapter): check that every method routes to the wrapped instance and not back through a registry/session/global, and that the wrapper forwards all the methods the callers actually use.

## Quality hunter
The cloud's code-quality pass. Its findings are `nit` unless they hide a bug.
- **Reuse**: re-implements an existing helper, or discards a value it already validated. Name the helper.
- **Simplification**: redundant or derivable state, near-duplicate code, deep nesting, dead code or options, docs that no longer match the code.
- **Efficiency**: repeated I/O, sequential independent work, blocking work on hot paths.
- **Altitude**: a symptom patched with a special case instead of fixing the shared mechanism.
- **Conventions**: rules in `~/.claude/CLAUDE.md`, the repo's `CLAUDE.md`/`AGENTS.md`, or an ancestor directory's `CLAUDE.md`. Flag only when you can quote the exact rule and the exact line.

## Sweep
One fresh hunter after all hunters return, given the verified list. It looks **only** for defects not already listed: moved/extracted code that dropped a guard or anchor; second-tier footguns (default evaluated once, `hash()` non-determinism, lock-scope shrink, predicate methods with side effects); setup/teardown asymmetry in tests; config defaults flipped. Up to 8 candidates, or none (don't pad).
