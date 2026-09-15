# Selective Multi-Model Routing for Claude Code

[Français](README.fr.md)

A project-scoped Claude Code configuration that hands work to specialized roles
only when delegation preserves quality while reducing total cost or latency. The
primary agent stays responsible for decisions, integration, and user
communication.

## Routing policy

Priorities, in order:

1. Preserve result quality and relevance.
2. Reduce total cost, including coordination and rework.
3. Reduce latency.

A lower total cost paid with more tokens on a cheaper tier is a good trade.
Degraded quality or multiplied latency is not.

Small, bounded tasks stay with the primary agent. Delegation is used when a
clearly scoped role can perform substantial work more efficiently or provide
useful independent analysis.

| Role | Model | Effort | $/1M in | $/1M out | Responsibility |
| --- | --- | --- | --- | --- | --- |
| Primary | `opus` | `xhigh` | 5 | 25 | Triage, decisions, integration, small local tasks |
| `scout` | `sonnet` | `medium` | 2 | 10 | Read-only codebase and log exploration |
| `researcher` | `sonnet` | `medium` | 2 | 10 | Multi-source external research |
| `runner` | `haiku` | *(unsupported)* | 1 | 5 | Long validations and large mechanical batches |
| `builder` | `sonnet` | `xhigh` | 2 | 10 | Scoped implementation with targeted validation |
| `architect` | `opus`, or `fable` on confirmed access | `xhigh` | 5 → 10 | 25 → 50 | Rare, bounded architecture decisions only |

Three choices deserve a justification:

- **`runner` on the cheapest tier.** The role executes and reports; it does not
  design. Its bounds — three fix/test cycles, stop on a repeated signal, two
  attempts on an environment problem — are exactly what makes this tier safe
  here. Haiku does not support `effort`, so the field is deliberately absent
  from its role file.
- **`scout` and `researcher` do not go down there.** Both produce facts the
  primary agent will believe without re-checking. Too low a tier yields
  confident, wrong claims whose rework costs more than the saving. Their effort
  stays `medium`: their work is bounded by input and output rather than by
  reasoning, and lower effort consolidates tool calls — cheaper and faster at
  equal quality.
- **`builder` raises effort rather than tier.** Effort is the first quality
  lever within a model; `sonnet`/`xhigh` costs two and a half times less than
  the tier above at `high`.

Two escalations exist, decided explicitly and passed at invocation without
editing any role file: `builder` to `opus` for an exceptionally hard task, and
`architect` to `fable` on confirmed access. An environment problem never raises
a tier.

## Claude Fable 5.1 access

Fable is not available to everyone, and it costs twice what Opus does. Depending
on plan and seat, its usage may be billed to *usage credits*; an interactive
session then asks for consent before billing, while a non-interactive run (`-p`)
bills without asking.

The configuration therefore **never** writes `fable` into a role file.
`architect` ships with `opus` at `xhigh`: it works on every plan and never
blocks a session. Escalation to Fable is dynamic and conditional.

Access is **presumed unavailable**, and determining it is deterministic:

```bash
claude auth status --json
```

`apiProvider`, `authMethod`, and `subscriptionType` settle nearly every case,
together with `claude --version` (Fable 5.1 requires 2.1.257 or newer) and
`availableModels` when it is set. The full decision table lives in the skill. An
unrecognized plan value is not interpreted — it is asked about.

Available still does not mean authorized. On a subscription, Fable may bill to
usage credits — money on top of the subscription. So the primary agent asks once
before the first consultation, naming the detected plan and the premium, and
records the answer in `.claude/settings.local.json` — gitignored, so it stays
per-machine.

Without access, or on refusal, `architect` answers on Opus 5 at `xhigh` and
**says explicitly that this is not a Fable opinion**. Afterwards the effective
model is checked in the call result (`resolvedModel`); without a match, the
result is discarded as non-conforming.

## Project layout

```text
.
├── CLAUDE.md
├── extract_claude_jsonl.ps1
├── test_extract_claude_jsonl.py
└── .claude/
    ├── settings.json
    ├── skills/quota-orchestrator/SKILL.md
    └── agents/
        ├── architect.md
        ├── builder.md
        ├── researcher.md
        ├── runner.md
        └── scout.md
```

- `CLAUDE.md` defines the repository-wide routing and safety rules.
- `quota-orchestrator` decides whether delegation is worth its full cost.
- `.claude/settings.json` sets default and per-model effort.
- `.claude/agents/*.md` defines each role's model, effort, tools, bounds, and
  reporting contract.
- `extract_claude_jsonl.ps1` measures what all of it actually consumes.

## Usage

### Inheritance and precedence

Claude Code builds its instruction chain from lowest to highest precedence:
organization-managed instructions, then `~/.claude/CLAUDE.md`, then the
repository root `CLAUDE.md`, then `CLAUDE.local.md`. A subdirectory's
`CLAUDE.md` loads on demand, when Claude works in it. The `@path` syntax imports
another file; relative paths resolve from the importing file, not the current
directory.

If your project already has a `CLAUDE.md`, **do not replace it**: keep its
contents and add the routing rules to it. To scope instructions to a
subdirectory, place another `CLAUDE.md` there.

For settings, `~/.claude/settings.json` provides your personal values. The
project's `.claude/settings.json` sits above it, `.claude/settings.local.json`
above that, and organization-managed settings take precedence over everything.

### Installation

1. Requires Python 3.11 or newer. From this repository, run:

   ```text
   python install.py path/to/your/project
   ```

   Use `--dry-run` to preview every change. The installer appends the routing
   rules to an existing `CLAUDE.md` between `claudeskills:routing` markers,
   adds only the missing `.claude/settings.json` keys, backs up modified files
   under `.claudeskills-backup/`, and warns instead of overwriting divergent
   role or skill files.
2. Review the warnings, then the models, efforts, and permission rules for your
   environment, then run `/agents` to confirm all five roles are seen with the
   right model and effort.
3. Start a new session from the repository so the instruction chain is rebuilt.
4. Ask Claude to summarize its active instructions if you want to verify
   discovery.

Claude Code discovers repository instructions from `CLAUDE.md`, skills from
`.claude/skills`, roles from `.claude/agents`, and settings from
`.claude/settings.json`. See the official documentation for
[CLAUDE.md](https://code.claude.com/docs/en/memory),
[skills](https://code.claude.com/docs/en/skills),
[subagents](https://code.claude.com/docs/en/sub-agents),
[models](https://code.claude.com/docs/en/model-config), and
[settings](https://code.claude.com/docs/en/settings).

## Measurement

Without measurement, a gain is expected, not demonstrated.
`extract_claude_jsonl.ps1` reads session JSONL transcripts and aggregates
tokens, durations, and **dollar cost** by model, by effort, and by role.

```powershell
.\extract_claude_jsonl.ps1
```

The report carries a `Complete` field. It is `true` only when no diagnostic was
raised. An incomplete report has exactly the status *not observable*: its
tokens, costs, and durations must never appear in a ratio, a median, a
comparison, or an economic recommendation. Compare at least two complete
reports, otherwise conclude that no comparison is possible.

The script reads two levels: the session transcript for the primary agent, and
`<session>/subagents/agent-*.jsonl` for each delegated role. That second source
is essential — the call result that spawned a subagent carries only its **final
turn**, not its total. Relying on it under-counts massively. A background
subagent is measured like any other; what makes a run unobservable is a missing
transcript, a model absent from the price table, or a cache write whose
time-to-live is unknown.

A second trap, also handled: one message appears once per content block and its
`usage` is **cumulative**. The script keeps the maximum per message id; keeping
the first would lose most of the output tokens.

A cache write is priced by its time-to-live: 1.25× input for a 5-minute cache,
**2× for a one-hour cache**. Claude Code uses both within a single session —
typically one hour for the primary agent and five minutes for a subagent.
Conflating them under-counts the bill by a third, so the script reads the
per-TTL breakdown and refuses to price a write whose TTL is unknown.

Prices live in a single table at the top of the script; that is the only place
to update when they change. `python test_extract_claude_jsonl.py` checks the
script's contract against synthetic transcripts, with no model calls.

## Safety boundaries

- Never run with `--dangerously-skip-permissions` or in `bypassPermissions` mode.
- Do not widen session permissions to consult `architect`; if its restrictions
  no longer hold, isolate the decision in another session.
- `architect` does not explore, execute commands, edit files, or delegate.
- Roles stay within their scope and do not perform routing themselves: `Agent`
  is absent from every role's tool list, which effectively prevents delegation.

## Customization

Edit `.claude/settings.json` for default efforts, and the matching file under
`.claude/agents/` to change a role. Keep models, efforts, and role boundaries
synchronized across `CLAUDE.md`, `quota-orchestrator/SKILL.md`, and this README.

The tiers proposed here are defensible, not measured on your work. The
measurement script exists precisely so you can tune them on your own tasks — and
the doctrine forbids claiming a demonstrated gain until two complete runs show it.

Model availability depends on your account and environment.
