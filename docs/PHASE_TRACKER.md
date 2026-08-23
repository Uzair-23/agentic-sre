# Phase Tracker — agentic-sre

Living document. Update the status and checkboxes as you go — don't mark a phase "Done" until its exit criteria are demonstrably true (run the actual check, don't infer it from the code looking right).

**Legend:** Not started · In progress · Done · Blocked

---

## Overview

| Phase | Name | Status | Target week |
|---|---|---|---|
| 0 | Project setup | Not started | Pre-week 1 |
| 1 | Core pipeline | Not started | Week 1-2 |
| 2 | Guardrails | Not started | Week 2-3 |
| 3 | Evals | Not started | Week 3-4 |
| 4 | Observability | Not started | Week 4 |
| 5 | UI | Not started | Week 5 |
| 6 | Postmortem loop | Not started | Week 6 |
| 7 | Resume-ready polish | Not started | Post-week 6 |

---

## Phase 0 — Project setup

**Status:** Done

**Goal:** repo, environment, and the shared-state schema exist before any agent logic is written.

**Description:** This phase has no agent behavior in it — it's the foundation everything else depends on. The shared `IncidentState` Pydantic model designed here is read and written by every agent in every later phase, so getting its fields right now avoids painful refactors later.

### Tasks

- [x] Create repo `agentic-sre` with the folder structure (`backend/`, `frontend/`, `docs/`, `.github/workflows/`)
- [x] Set up Python env (`poetry`/`venv`), install core deps (`langgraph`, `langchain-groq`, `fastapi`, `uvicorn`, `pydantic`, `langfuse`, `presidio-analyzer`)
- [x] Get Groq API key (free tier), store in `.env`, add `.env.example`
- [x] Set up `docker-compose.yml` for self-hosted Langfuse + Postgres, confirm it runs
- [x] Set up Node/Vite for the frontend shell
- [x] Define `IncidentState` Pydantic model in `agents/schemas.py`
- [x] Copy `docs/PRD.md`, `docs/implementation_plan.md`, `CLAUDE.md` into the repo

### Exit criteria

- [x] `docker compose up` brings up Langfuse locally without errors
- [x] `IncidentState` model is defined and imports cleanly
- [x] A "hello world" LangGraph graph with one dummy node runs end to end against Groq

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Phase 1 — Core pipeline

**Status:** Done

**Goal:** Monitor → Diagnosis → Remediation working end-to-end on hardcoded synthetic incidents. No UI, no guardrails yet — just prove the hand-off works.

**Description:** This is where the actual multi-agent behavior comes alive. Each agent is built and tested individually against 2-3 hand-written synthetic incidents before wiring them together in LangGraph. The Monitor agent pairs a deterministic statistical check with LLM interpretation — don't let the LLM freely decide what counts as an anomaly. All agent outputs must be structured (Pydantic), never free-text parsed.

### Tasks

- [x] Build `simulator/incident_generator.py` — 3 incident types (memory leak, bad deploy, dependency timeout)
- [x] Build Monitor agent (`agents/monitor.py`) — read-only log query tool + z-score anomaly check + LLM interpretation
- [x] Build Diagnosis agent (`agents/diagnosis.py`) — deploy-history + dependency-graph tools, structured output with confidence score
- [x] Build Remediation agent (`agents/remediation.py`) — action-enum-constrained proposal tool, no execution capability
- [x] Wire Monitor → Diagnosis → Remediation in `agents/graph.py` (LangGraph)
- [x] Run end-to-end on all 3 hardcoded incidents, manually sanity-check each output

### Exit criteria

- [x] One script run produces a diagnosis + proposed fix a human would find reasonable, for all 3 seed incidents
- [x] All agent outputs are structured Pydantic objects, not parsed free text

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Phase 2 — Guardrails

**Status:** Done

**Goal:** no agent can reach "execution" without passing through explicit checks.

**Description:** This phase is what differentiates the project from a typical agent demo. Every guardrail needs a corresponding test that actively tries to break it — a happy-path-only test doesn't prove anything. The Approval gate must be a real LangGraph interrupt node, not a faked sleep/poll loop.

### Tasks

- [x] Build `guardrails/action_schema.py` — strict enum + param validation for every action type
- [x] Build `guardrails/risk_classifier.py` — tags proposals `low`/`medium`/`high` based on action type + target
- [x] Insert a real Approval gate node in the LangGraph pipeline (human-in-the-loop interrupt)
- [x] Wire rejection routing — rejected proposals go back to Diagnosis agent with `approval_notes`
- [x] Build `guardrails/injection_guard.py` + a seeded incident with an embedded instruction in a log line; write an automated test proving Diagnosis agent doesn't follow it
- [x] Wire Presidio into the log pipeline for PII scrubbing before anything hits the LLM or gets logged

### Exit criteria

- [x] Live demo: a `high` risk action cannot execute without approval
- [x] Automated test proves a malicious/injected log line doesn't hijack Diagnosis agent
- [x] Automated test proves a malformed/free-text action proposal is rejected, not coerced

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Phase 3 — Evals

**Status:** Done

**Goal:** quantitative, automated scoring of the whole pipeline — the phase that most differentiates this project.

**Description:** The golden set is the source of truth for "does this system work" — incomplete or lazy ground-truth entries will quietly break scoring later, so don't rush this. LLM-judge prompts should log their justification alongside the score so disagreements are debuggable. The CI regression suite is the single most interview-worthy artifact in the project — it should visibly block a regressing PR at least once before you're done.

### Tasks

- [x] Build `simulator/golden_set.json` — 15-20 incidents with ground-truth root cause, fix, and risk level, including 2-3 "trick" cases
- [x] Build `evals/harness.py` — runs full pipeline against golden set, auto-approving in eval mode, capturing diagnosis/fix/risk/latency/cost
- [x] Build `evals/judges.py` — LLM-judge scoring for semantic match on `root_cause_hypothesis`, with logged justification
- [x] Compute aggregate metrics: diagnosis accuracy, fix correctness, confidence calibration, false-positive rate
- [x] Build `evals/run_regression.py` + `evals/baseline.json`
- [x] Wire `.github/workflows/eval.yml` to run the suite on every push/PR and fail the build below threshold

### Exit criteria

- [x] `python evals/run_regression.py` outputs a full scorecard locally
- [x] CI is wired and has caught at least one real regression (screenshot/log this for later)

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Phase 4 — Observability

**Status:** Done

**Goal:** every agent decision is traceable end to end.

**Description:** Every new agent node must be wrapped with the Langfuse tracing callback — an untraced node breaks the audit story this whole project is selling. Eval-harness runs should be tagged distinctly from real/demo runs so the Langfuse UI stays useful for debugging rather than cluttering the real runs.

### Tasks

- [ ] Wire `observability/tracing.py` — Langfuse callback wrapping every LangGraph node
- [x] Tag every trace with `incident_id`
- [x] Verify traces are complete in Langfuse's built-in UI before building anything custom
- [x] Tag eval-harness runs with `session=eval_regression` so they're filterable from real runs
- [x] Confirm cost-per-incident and latency-per-agent are visible in the dashboard

### Exit criteria

- [x] Search Langfuse by `incident_id`, see the complete Monitor→Diagnosis→Remediation→Approval trace with cost and latency per step

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Phase 5 — UI

**Status:** Done

**Goal:** a demoable dashboard — makes the interview conversation visual, not "trust me, it works."

**Description:** The Approval panel's typed-confirmation flow for high-risk actions is a guardrail requirement, not a design nicety — don't simplify it away under time pressure. A "replay" button that re-runs a golden incident live is what makes this demoable on demand in an interview without needing a real outage.

### Tasks

- [x] Build FastAPI endpoints: `POST /incidents/simulate`, `GET /incidents/{id}`, `POST /incidents/{id}/approve`, `POST /incidents/{id}/reject`, `GET /incidents/{id}/trace`
- [x] Build incident feed (list view with status badges)
- [x] Build incident detail view — renders the `event_log` as a timeline
- [x] Build Approval panel — risk badge + typed confirmation for `high` risk
- [x] Build/link Trace viewer (embed or link out to Langfuse)
- [x] Add a "replay golden incident" button for live demos

### Exit criteria

- [x] Open the dashboard, click "simulate incident," watch the feed populate live, approve/reject, open the trace — all without touching the terminal

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Phase 6 — Postmortem loop

**Status:** Done

**Goal:** close the loop — the system demonstrably learns from what happened.

**Description:** No model weights change here — the "learning" is a config adjustment (Monitor agent's alert thresholds) that a later run visibly picks up. This is a small phase but an important one for the story: it's what separates "a pipeline" from "a system with memory."

### Tasks

- [x] Build Postmortem agent (`agents/postmortem.py`) — reads full `event_log`, writes structured report + threshold adjustment
- [x] Build a small config store for threshold adjustments that Monitor agent reads on each run
- [x] Run two related incidents back to back, confirm the second is detected differently/faster because of the first's postmortem

### Exit criteria

- [x] Demonstrable, repeatable proof that a postmortem measurably changes a later Monitor agent run

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Phase 7 — Resume-ready polish

**Status:** Not started

**Goal:** the repo is something you'd actually hand to a hiring manager.

### Tasks

- [ ] README with architecture diagram, setup instructions, 2-minute demo GIF/video
- [ ] At least one CI run visibly showing a caught eval regression (screenshot or link)
- [ ] Golden set + eval scorecard checked into the repo
- [ ] README "guardrails" section explicitly listing what's blocked and why
- [ ] Trace screenshots or short video walkthrough of the Langfuse dashboard
- [ ] One-paragraph interview pitch written and rehearsed (lead with the guardrail/approval-gate story, not the tech stack list)

### Exit criteria

- [ ] Someone with no context can read the README in 3 minutes and understand what the project proves

### Notes / blockers

*_(add anything you hit here as you go)_*

---

## Change log

*_(Use this to note major pivots or scope changes as you build — useful both for your own memory and as an interview talking point ("here's a decision I changed mid-build and why").)*

| Date | Change | Reason |
|---|---|---|
| | | |