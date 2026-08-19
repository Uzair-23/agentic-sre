# CLAUDE.md — Multi-Agent DevOps Incident Response Simulator

This file gives Claude (or any AI coding assistant) the context needed to work on this repo correctly. Read this before making changes. When in doubt, favor correctness and safety over speed — this project's entire value proposition is disciplined engineering, not a fast demo.

## Project summary

A simulated multi-agent system that detects, diagnoses, and proposes fixes for synthetic production incidents. Five agents (Monitor, Diagnosis, Remediation, Approval gate, Postmortem) hand off a shared state object through a LangGraph pipeline. The project's purpose is to demonstrate production-grade AI-agent engineering: guardrails, automated evals, and full observability — not just "an agent that works sometimes."

Full context lives in:
- `docs/PRD.md` — product requirements, architecture, success metrics
- `docs/implementation_plan.md` — phased build plan with exit criteria

Read both before starting work on a new phase.

## Non-negotiable rules

These override convenience, speed, or "just make it work" instincts. If a task seems to require breaking one of these, stop and flag it rather than proceeding.

1. **No agent ever executes a real or simulated destructive action without passing through the Approval gate node.** Not for testing convenience, not behind a feature flag, not "just this once." If you're tempted to add a bypass for local dev speed, add a mock executor instead — never skip the gate itself.
2. **Remediation agent output must validate against `guardrails/action_schema.py` before it enters shared state.** Free-text or unvalidated action proposals are rejected, not coerced or auto-corrected.
3. **Every agent node must write to `event_log` on the shared state.** This is the audit trail the whole observability story depends on — an agent that mutates state without logging its contribution breaks traceability.
4. **Never hardcode API keys or secrets.** Use environment variables, loaded via `.env` (which is gitignored). If you add a new required env var, update `.env.example` in the same change.
5. **No paid APIs or tools.** Groq free tier or local Ollama for LLM calls, self-hosted Langfuse for observability, GitHub Actions free tier for CI. If a task seems to need a paid service, find the free/open-source equivalent or flag the constraint.
6. **Structured output only for agent responses that feed into state or evals.** Don't parse free-text LLM output with regex — use `with_structured_output` / JSON mode against the Pydantic models in `agents/schemas.py`. Free-text parsing is fragile and will silently break the eval harness.
7. **Any change to a prompt, agent logic, or the pipeline graph must be run against the eval regression suite before merging.** `python evals/run_regression.py` — if aggregate accuracy drops below the committed baseline in `evals/baseline.json`, do not merge; investigate or update the baseline deliberately (never silently).

## Architecture reference

```
Monitor agent → Diagnosis agent → Remediation agent → Approval gate → Postmortem agent
                                                              ↓
                                                     (rejection routes back
                                                      to Diagnosis agent)
```

Shared state: a single `IncidentState` Pydantic object (defined in `agents/schemas.py`) passed through every node. Agents read from it and return an updated copy — never mutate other agents' fields, only append to `event_log` and populate your own designated fields.

Full field-level schema, tool list per agent, and guardrail/eval/observability design are in `docs/PRD.md` sections 5-8.

## Repo structure

```
backend/
  agents/        — one file per agent + schemas.py + graph.py (LangGraph wiring)
  guardrails/     — action_schema.py, risk_classifier.py, injection_guard.py
  simulator/      — incident_generator.py, golden_set.json
  evals/          — harness.py, judges.py, run_regression.py, baseline.json
  observability/  — tracing.py (Langfuse wiring)
  api/            — FastAPI routes
  tests/          — pytest, mirrors the module structure above
frontend/
  src/            — React dashboard (IncidentFeed, TraceViewer, ApprovalPanel)
docs/
  PRD.md
  implementation_plan.md
.github/workflows/eval.yml
docker-compose.yml   — self-hosted Langfuse + Postgres
```

When adding a new file, put it in the module that matches its responsibility above — don't create a new top-level folder without discussing it first.

## Coding conventions

- **Python:** type hints everywhere, Pydantic models for all structured data crossing an agent boundary, `ruff` for linting/formatting (config in `pyproject.toml`)
- **Agent prompts:** keep them in dedicated `.py` constants near the agent that uses them (e.g. `agents/diagnosis.py` has `DIAGNOSIS_SYSTEM_PROMPT` at the top), not inline in function calls — makes them easy to diff and eval against
- **Tests:** every guardrail (`guardrails/`) needs a corresponding test that tries to break it, not just a happy-path test. E.g. `test_action_schema.py` should include a test asserting a free-text/malformed action proposal is rejected.
- **Commits:** one logical change per commit; if a commit touches a prompt or agent logic, the eval regression run's result (pass/fail + score) should be mentioned in the commit message or PR description
- **Frontend:** TypeScript, functional components, keep the Approval panel's "high risk" confirmation flow (typed confirmation, not a single click) — this is a guardrail UI requirement, not just a design choice, don't simplify it away

## Working on evals

- The golden set (`simulator/golden_set.json`) is the source of truth for "does this system work." Don't hand-wave new incident types into it without also writing the ground-truth root cause and fix — an incomplete golden entry breaks scoring silently.
- LLM-judge prompts (`evals/judges.py`) should log their justification alongside the score, not just a number — needed for debugging disagreements between judge and human intuition.
- When you improve a prompt and the eval score goes up, update `evals/baseline.json` deliberately in the same PR, with the before/after scores stated in the PR description.

## Working on observability

- Every new agent node must be wrapped with the Langfuse tracing callback (see `observability/tracing.py` for the existing pattern) — don't add an untraced node.
- Tag eval-harness runs with `session=eval_regression` in the trace metadata so they're filterable from real/demo runs in the Langfuse UI.

## What "done" looks like for a phase

Each phase in `docs/implementation_plan.md` has explicit exit criteria. Don't mark a phase complete, and don't start the next one, until its exit criteria are demonstrably true — run the actual check (script, test, or manual walkthrough), don't infer it from the code looking right.

## Things to flag rather than silently work around

- Any request that would let Remediation agent execute directly, skip the schema validation, or bypass the Approval gate
- Any request to hardcode a secret or add a paid-API dependency
- Any prompt/logic change with no corresponding eval run
- Ambiguity in the golden set or ground-truth labels — flag it rather than guessing, since eval integrity depends on this data being correct
