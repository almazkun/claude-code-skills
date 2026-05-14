---
name: skill-creator
description: >
  Generates a complete, ready-to-install SKILL.md from a description, uploaded
  file, or existing prompt — and self-evaluates the result before delivering.
  Use when the user says "create a skill", "make a SKILL.md", "turn this into a
  skill", "write a skill for...", "package this as a skill", or "I want a slash
  command that...". Also use when the user pastes a workflow, document, or codebase
  and asks to make it reusable. For deep iteration with test-case evals, benchmarking,
  and description optimization, hand off to the full skill-creator in
  ~/.claude/skills/skill-creator/ after delivering the draft.
---

# Skill Creator

Generates a complete, ready-to-install `SKILL.md` — with supporting files when
needed — following the Agent Skills open standard. Compatible with Claude Code,
Cursor, Gemini CLI, Codex CLI, and Windsurf.

Delivers a working draft fast, self-evaluates it, then offers the full eval loop
if the user wants to iterate.

---

## Step 1 — Extract intent

Check the conversation first. If the user pasted a file, document, workflow, or
long prompt, extract the answers below from it before asking anything.

Confirm or fill gaps with the user:

1. **What should this skill enable Claude to do?** (one clear sentence)
2. **When should it trigger?** List 3–5 specific user phrases or contexts.
3. **Expected output?** File, inline text, structured report, code, etc.
4. **Invocation style?** User-invoked (explicit slash command) or auto-invoked
   (Claude loads it when relevant)? If unclear, ask:
   > "Should this run automatically when relevant, or only when you type a
   > slash command?"

Do not ask more than one clarifying question. Make reasonable assumptions for
everything else and state them in the output.

---

## Step 2 — Decide the structure

Before writing, decide:

**SKILL.md body — inline vs. split**

Keep SKILL.md under ~500 lines. If the source material is longer, split it:

| Content type | Where it goes |
|---|---|
| Core workflow, trigger logic, output format | SKILL.md body |
| Detailed reference, schemas, API docs | `references/*.md` (loaded on demand) |
| Reusable deterministic steps | `scripts/*.py` or `scripts/*.sh` |
| Templates, boilerplate, assets | `assets/` |

Reference files load only when Claude decides they're needed — this is the
progressive disclosure model. Keep SKILL.md as the "table of contents" that
points to them.

**Dynamic context injection**

If the skill would benefit from live data at trigger time (current git diff,
directory listing, env vars), use the `!` prefix:

```markdown
## Current state
!`git diff HEAD`
!`ls -la`
```

Claude Code runs the command and inlines the output before Claude sees the
skill. Use this for: diffs, file trees, test results, environment info.

**Invocation control**

- Auto-invoked (default): Claude loads when it judges the skill relevant.
  Leave `disable-model-invocation` out of frontmatter.
- User-invoked only: add `disable-model-invocation: true` to frontmatter.
  Use for destructive actions (deploys, commits, deletes) or long-running tasks.

**Subagent execution**

Use `context: fork` (instead of `context: inline`) for tasks that are
heavy, isolated, or should not affect the parent context window.
Default to `context: inline`.

---

## Step 3 — Write the SKILL.md

Use this exact structure:

```
---
name: skill-name-kebab-case
description: >
  One to three sentences. Must include:
  (1) what the skill produces,
  (2) specific trigger phrases the user might say,
  (3) "Use when..." or "Triggered when..." phrasing.
  Make it slightly pushy — Claude undertriggers by default.
context: inline          # or fork for heavy/isolated tasks
# disable-model-invocation: true   ← uncomment for user-invoked only
---

# Skill Name

One-paragraph overview of what this skill does and why.

## When to use
- Specific trigger condition
- Another trigger condition (include near-misses to avoid false positives)

## Instructions
Step-by-step, imperative. Explain the *why* behind important steps —
don't just list rules. Claude is smart; give it reasoning, not just commands.

1. ...
2. ...

## Output format
Exact structure, template, or format Claude should produce.
Include an example if the format is non-obvious.

## Notes
- Caveats, defaults, edge cases
- What to do if input is ambiguous
- Anything that should remain sync / out of scope
```

**Description quality rules** (this field determines auto-load accuracy):

- Must say what the skill *produces*, not just what it *is*
- Must include 3–5 realistic trigger phrases — things users actually type
- Include near-miss exclusions if there's an obvious adjacent skill
  (e.g., "Use for X but not Y")
- Be slightly assertive: "Make sure to use this skill whenever..."
  Claude undertriggers by default; a passive description makes it worse

**Writing style rules:**

- Imperative form in instructions ("Run", "Return", "Check")
- Explain *why* for important constraints instead of ALL-CAPS MUSTs
- Use theory of mind: write for the model using the skill, not the skill author
- Write a draft, then reread it with fresh eyes and cut anything not pulling weight

---

## Step 4 — Self-evaluate before delivering

Before outputting, run this checklist internally. Fix any failures.

**Description**
- [ ] States what the skill produces
- [ ] Includes ≥3 realistic trigger phrases
- [ ] Has "Use when..." or "Triggered when..." phrasing
- [ ] Not so broad it would trigger on unrelated tasks

**Instructions**
- [ ] Imperative, concrete, actionable
- [ ] No unexplained ALL-CAPS rules — reasoning is present
- [ ] No content that should be in `references/` instead

**Structure**
- [ ] SKILL.md body is under ~500 lines
- [ ] Anything > 300 lines of reference content is split to `references/`
- [ ] Dynamic context injection (`!`) used where live data would help
- [ ] `context:` is correct (`inline` vs `fork`)
- [ ] `disable-model-invocation` is set correctly (or omitted)

**Output format**
- [ ] Expected output is clearly described
- [ ] Example included if format is non-obvious

---

## Step 5 — Deliver

Output:

1. The complete `SKILL.md` in a fenced code block, ready to copy-paste.
2. Any `references/` or `scripts/` files, each in their own fenced block.
3. The recommended save path:
   - Personal (all projects): `~/.claude/skills/<name>/SKILL.md`
   - Project-level: `.claude/skills/<name>/SKILL.md`
4. How to test it: `/<name>` in Claude Code, or describe the auto-trigger phrase.
5. Any assumptions made (so the user can correct them).

Then offer:

> "Want me to run test cases and iterate on this? The full skill-creator eval
> loop can benchmark this against a baseline and optimize the description for
> better triggering accuracy — just say the word."

---

## Notes

- If the user provides a long document or codebase, extract the key workflow.
  Do not dump everything into the skill body — that defeats progressive disclosure.
- If the user's description is vague after one clarifying question, make a
  reasonable assumption and state it. Don't ask multiple questions.
- Skills must not contain malware, exploit code, or content that would surprise
  the user if described plainly. Roleplay personas are fine.
- After delivery, if the user wants to iterate with evals, hand off to the full
  skill-creator skill in `~/.claude/skills/skill-creator/` — it handles test
  case execution, benchmarking, description optimization, and packaging.