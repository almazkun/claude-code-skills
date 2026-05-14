# claude-code-skills
Claude Code Skills

## Usage
Copy skill directories to your Claude Code Skill directory, usually `~/.claude/skills/`
```sh
git clone git@github.com:almazkun/claude-code-skills.git
ln -s $(pwd)/claude-code-skills/async-python-django-ninja ~/.claude/skills/async-python-django-ninja
```
## What Are Claude Code Skills?

Skills extend Claude's capabilities by packaging expertise into composable resources, transforming general-purpose agents into specialized agents. Building a skill for an agent is like putting together an onboarding guide for a new hire.

Skills are reusable instruction packages that teach an AI agent how to handle a specific class of tasks. Each skill is a folder containing a `SKILL.md` file with YAML frontmatter (name, description) and Markdown instructions, optionally bundled with scripts, references, and assets. Anthropic introduced the format in October 2025 and released it as an open standard in December 2025; it's now supported by Claude Code, Claude.ai, the Claude API, OpenAI Codex, Cursor, Gemini CLI, and Windsurf.

---

## How Skills Load (Progressive Disclosure)

Skills load progressively. At session start, the agent sees only each skill's name and description — roughly 100 tokens per skill. The full `SKILL.md` body (typically under 5,000 tokens) loads only when the agent decides the skill is relevant to the current task. Auxiliary files in `scripts/` and `references/` load on demand. This is what lets a single agent host hundreds of skills without bloating its context window.

---

## Skill Structure in Claude Code

Skills are configured through YAML frontmatter at the top of `SKILL.md`. The directory name becomes the command you type, and the description helps Claude decide when to load the skill automatically.

A file at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way. Skills add optional features: a directory for supporting files, frontmatter to control whether you or Claude invokes them, and the ability for Claude to load them automatically when relevant.

**Dynamic context injection** is a powerful feature: The `!`git diff HEAD`` line uses dynamic context injection — Claude Code runs the command and replaces the line with its output before Claude sees the skill content, so the instructions arrive with the current diff already inlined.

---

## Bundled Skills

Claude Code includes a set of bundled skills available in every session, including `/simplify`, `/batch`, `/debug`, `/loop`, and `/claude-api`. Unlike most built-in commands which execute fixed logic directly, bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools.

---

## Two Categories of Skills

There's an important distinction between two categories. **Capability Uplift** skills give Claude abilities it doesn't have on its own — before the skill, Claude can't do the task. **Encoded Preference** skills are different: Claude already knows how to do the underlying task, but the skill encodes your team's specific way of doing it (NDA reviews, commit message formats, code review checklists, etc.).

---

## Skill Scoping & Priority

Where you store a skill determines who can use it. When skills share the same name across levels, enterprise overrides personal, and personal overrides project. Plugin skills use a `plugin-name:skill-name` namespace so they cannot conflict with other levels.

---

## Token Efficiency

Skills dramatically reduce token usage compared to providing instructions in prompts. For example, creating an Excel file with formatting: without skills requires ~8,000 tokens to explain all Excel features upfront; with skills, there's minimal metadata overhead initially, and ~5,000 tokens only when the Excel skill is invoked.

---

## Availability

Skills are available for users on Free, Pro, Max, Team, and Enterprise plans, but require code execution to be enabled. Skills are also available in beta for Claude Code users and for all API users using the code execution tool.

---

## Security Note

The most significant risks are prompt injection and data exfiltration caused by malicious package code. Anthropic has implemented several mitigations. Only install skills from trusted sources — when installing a skill from a less-trusted source, review it before enabling by reading the contents of the bundled files, paying particular attention to code dependencies and bundled resources like images or scripts.
