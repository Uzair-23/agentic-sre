# PRD — agentic-sre

**Owner:** Uzair
**Status:** Draft v1
**Type:** Portfolio project — AI Engineer / AI Full-Stack
**Repo name:** agentic-sre
**Subtitle:** Multi-Agent DevOps Incident Response Simulator

---

## 1. Problem statement

When production systems fail, on-call engineers spend the first 10-20 minutes just figuring out *what* broke and *where* — before they can even start fixing it. AI-SRE agents (a fast-growing, VC-funded category) aim to compress that window by having agents monitor, diagnose, and propose fixes automatically, while keeping a human in control of anything destructive.

This project simulates that workflow end-to-end: a pipeline of cooperating agents that detects a synthetic incident, diagnoses the root cause, proposes a remediation, waits for human approval before acting, and writes a postmortem — with guardrails, evals, and observability built in from day one, not bolted on after.

## 2. Goals

- Build a working multi-agent pipeline demonstrating agent hand-offs, shared state, and tool use
- Demonstrate production-grade safety: no agent can take a destructive action without going through an approval gate
- Build a real eval harness that measures agent performance quantitatively, not just "it seems to work"
- Instrument full observability so every decision an agent makes is traceable
- Ship a UI dashboard so the system is demoable in an interview, not just a script in a terminal

## 3. Non-goals

- Not connecting to a real production environment — all incidents are synthetic (seeded log/metric streams)
- Not building a general-purpose agent framework — scope is one well-defined incident-response workflow
- Not optimizing for scale/throughput — optimizing for correctness, safety, and explainability

## 4. Users / personas

- **Primary:** hiring managers and interviewers evaluating AI-engineering depth from a portfolio
- **Simulated end user (in-product):** an on-call engineer who receives an alert, reviews the agent's diagnosis and proposed fix, and approves or rejects it

## 5. System architecture

### 5.1 Agent pipeline

| Agent | Responsibility | Tools available |
|---|---|---|
| Monitor agent | Watches a synthetic metrics/log stream, detects anomalies, raises an incident | Log/metric query tool (read-only) |
| Diagnosis agent | Investigates the incident, correlates logs/metrics/recent deploys, determines probable root cause | Log query, deploy-history query, service-dependency graph lookup |
| Remediation agent | Proposes a fix (e.g. rollback, restart, scale-up, config change) with a written justification | Command-proposal tool only — cannot execute |
| Approval gate | Human-in-the-loop checkpoint — engineer reviews diagnosis + proposed fix, approves/edits/rejects | N/A (human interface) |
| Postmortem agent | Writes a structured incident report once resolved, and updates Monitor agent's alert thresholds based on what was learned | Report-writing, threshold-update tool |

### 5.2 Data flow

1. Synthetic incident generator seeds an anomaly into the log/metric stream
2. Monitor agent polls the stream, flags anomaly, opens an incident record with shared state (`incident_id`, `symptoms`, `timestamp`)
3. Diagnosis agent reads the incident state, investigates, appends `root_cause_hypothesis` + `confidence_score` to shared state
4. Remediation agent reads diagnosis, proposes `fix_plan` (structured object: action, target, risk_level) to shared state
5. Approval gate surfaces the full state (symptoms → diagnosis → proposed fix) to the human via the dashboard
6. On approval, a (simulated) executor "applies" the fix; on rejection, state routes back to Diagnosis agent with the rejection reason for a second pass
7. Postmortem agent reads the full incident timeline, writes the report, and proposes a threshold adjustment for Monitor agent

### 5.3 Shared state

A single incident-state object passed between agents (not separate memory per agent) — this is what makes it genuinely multi-agent rather than a single agent calling different prompts. Store as a structured JSON object with an append-only event log, so every agent's contribution is independently auditable.

### 5.4 Worked example — one incident end to end

This section traces a single synthetic incident through the full pipeline, showing exactly what data enters and leaves each agent. Use this as the reference example when writing tests, golden-set entries, or explaining the system in an interview.

**Input — synthetic log/metric stream (from the incident generator):**
```
[10:02:01] payment-service: memory usage 62%
[10:14:33] payment-service: memory usage 84%
[10:14:40] payment-service: deploy event — v2.3.1 rolled out at 09:58
[10:19:12] payment-service: memory usage 96%
[10:19:45] payment-service: OOMKilled, restarting
```

**Step 1 — Monitor agent.** A deterministic statistical check (z-score on memory usage) flags the spike first — the LLM is never asked to eyeball raw noise and guess whether it's anomalous. Once flagged, the agent's job is to interpret the signal and open the incident record:
```json
{
  "incident_id": "inc_0091",
  "symptoms": ["memory usage climbing steadily", "OOMKilled restart on payment-service"],
  "raw_signals": { "service": "payment-service", "metric": "memory", "peak": "96%" }
}
```

**Step 2 — Diagnosis agent.** Reads `symptoms` + `raw_signals`, queries deploy history and the service-dependency graph, and correlates the spike against the deploy timestamp. Must output a confidence score; below threshold, the pipeline routes to "needs more investigation" instead of letting Remediation agent guess:
```json
{
  "root_cause_hypothesis": "Memory leak introduced in deploy v2.3.1",
  "confidence_score": 0.87,
  "evidence": ["deploy timestamp precedes memory climb by ~4 min", "no other services show anomalies"]
}
```

**Step 3 — Remediation agent.** Picks an action from the fixed enum (`rollback`, `restart_service`, `scale_up`, `toggle_config_flag`) — never free text — and writes a justification. The proposal is validated against the action schema before it's accepted into state:
```json
{
  "proposed_fix": {
    "action_type": "rollback",
    "target": "payment-service",
    "params": { "to_version": "v2.3.0" }
  },
  "justification": "Memory growth correlates directly with the v2.3.1 deploy; rollback is the fastest safe mitigation."
}
```
The risk classifier tags this `high` risk (payment-service is a critical path), which determines the approval UI's confirmation requirements in the next step.

**Step 4 — Approval gate.** Not an agent decision — a hard stop. The pipeline pauses (LangGraph human-in-the-loop interrupt) and the dashboard shows symptoms → diagnosis → proposed fix → risk badge. Because this is `high` risk, the engineer must type the action name to confirm rather than click a single button.
- **Approve:** `approval_status: "approved"`, simulated executor logs "action applied," incident moves to resolved.
- **Reject:** `approval_status: "rejected"` with notes, and state routes *back* to the Diagnosis agent for a second pass — the one non-linear branch in the flow.

No path exists for any agent to bypass this gate — it is the core guardrail the project is built to prove.

**Step 5 — Postmortem agent.** Reads the full `event_log` for the resolved incident, writes a structured report, and proposes a Monitor-agent threshold adjustment:
```json
{
  "postmortem": "Incident inc_0091: memory leak from deploy v2.3.1, detected in 17 min, resolved via rollback...",
  "threshold_adjustment": { "service": "payment-service", "metric": "memory", "sensitivity": "+15%" }
}
```
This adjustment is written to a small config store that the Monitor agent reads on its next run — the feedback loop. The system's config becomes more sensitive over time; no model weights change.

**Final output — three artifacts per incident, plus one aggregate artifact:**
1. A resolved `IncidentState` object — the complete audit trail, viewable on the dashboard's incident detail page
2. A Langfuse trace — every agent call, tool call, latency, and token cost, searchable by `incident_id`
3. A postmortem report + updated Monitor threshold — feeds into the next incident, closing the loop
4. (Aggregate, across the golden set) An eval scorecard — diagnosis accuracy, fix correctness, false-positive rate — produced by the eval harness, not this single run

## 6. Guardrails

- **Hard action gate:** Remediation agent can only ever *propose* an action object — no agent has execution privileges except the (simulated) executor, which only fires after explicit human approval
- **Blast-radius classification:** every proposed fix is tagged `low` / `medium` / `high` risk by a separate classifier step; `high` risk proposals require an explicit typed confirmation, not just a button click
- **Command allowlist:** proposed actions must match a predefined schema (rollback, restart, scale, config-flag-toggle) — free-text shell commands are rejected outright
- **Prompt-injection defense:** if log/metric data is ever treated as untrusted input (e.g. simulating a compromised service emitting malicious log lines), test that the Diagnosis agent doesn't follow instructions embedded in log content
- **Confidence floor:** Diagnosis agent must report a confidence score; below a threshold, the pipeline routes to "needs more investigation" instead of letting Remediation agent guess

## 7. Evals

- **Golden incident set:** 15-20 synthetic incidents with known root causes and known-good fixes, covering different failure classes (memory leak, bad deploy, dependency timeout, config drift)
- **Diagnosis accuracy:** does the agent's root-cause hypothesis match the seeded ground truth (LLM-judge scoring + exact-match on structured fields)
- **Remediation correctness:** does the proposed fix match (or reasonably approximate) the known-good fix
- **Mean time-to-diagnosis:** measured in pipeline steps/latency across the golden set
- **False-positive rate:** how often Monitor agent raises an incident on injected non-anomalous noise
- **Regression suite:** all of the above run automatically (GitHub Actions, free tier) on every prompt/pipeline change, so you can show a before/after eval score delta — this is a very strong interview artifact

## 8. Observability

- Full distributed trace per incident: every agent step, tool call, latency, and token cost, using Langfuse (self-hosted, free/open-source) or OpenTelemetry + Jaeger
- Dashboard view showing the incident timeline as a trace graph — this is the single best demo artifact of the whole project
- Cost-per-incident and latency-per-agent metrics, aggregated across the golden eval set

## 9. Tech stack (all free/open-source)

### Agent orchestration

| Tool | Use |
|---|---|
| LangGraph | Core orchestration engine — defines each agent as a node, wires the Monitor → Diagnosis → Remediation → Approval → Postmortem flow as a graph, and passes the shared `IncidentState` object between nodes. Its human-in-the-loop interrupt feature makes the Approval gate a real pause-and-wait step rather than a fake sleep loop. This is the single most important architectural choice in the project — it's what makes it a genuine multi-agent system instead of one long prompt chain. |
| LangChain | Underlying LLM call abstraction LangGraph builds on — handles prompt templates, structured-output parsing (`with_structured_output`), and tool-calling interfaces for each agent. |

### LLM inference (free)

| Tool | Use |
|---|---|
| Groq API (free tier) | Runs Llama 3.3 for all agent reasoning — fast inference, generous free tier for a portfolio project. Primary LLM. |
| Ollama (local, optional fallback) | Runs open models (Llama/Qwen) entirely on-machine — backup for Groq rate limits, and useful for offline dev/testing without burning API calls while iterating on prompts. |

### Data validation

| Tool | Use |
|---|---|
| Pydantic | Defines every structured object crossing an agent boundary — `IncidentState`, `FixProposal`, action schemas. Makes "structured output only" enforceable rather than aspirational; an agent's output either validates or gets rejected, no silent free-text parsing. |

### Guardrails

| Tool | Use |
|---|---|
| Microsoft Presidio | PII detection/redaction — scrubs fake user data (emails, IPs) out of synthetic logs before they hit the LLM or get logged, demonstrating real data-handling discipline even in a simulator. |
| Custom rules (no library) | The action-schema enum, risk classifier, and prompt-injection test are hand-written, not a third-party guardrails framework — deliberately, since building these yourself proves you understand the mechanism rather than just calling a library. |

### Evals

| Tool | Use |
|---|---|
| Custom eval harness (`harness.py` + `judges.py`) | Runs the pipeline against the golden incident set and scores diagnosis accuracy, fix correctness, and confidence calibration. Written custom rather than fully outsourced to a framework so every scoring decision is explainable in an interview. |
| RAGAS / DeepEval (referenced patterns) | Open-source eval libraries to borrow scoring patterns from (e.g. LLM-as-judge rubric design) — not adopted wholesale, but free and worth pulling ideas from for a faster start. |
| GitHub Actions (free tier) | Runs the eval regression suite automatically on every push/PR — turns "I have an eval script" into "I have CI-gated quality control." |

### Observability

| Tool | Use |
|---|---|
| Langfuse (self-hosted via Docker) | Full tracing for every agent call — captures prompt, response, latency, and token cost per node, tagged by `incident_id`. The project's demo centerpiece: opening a trace and walking through exactly what each agent saw and decided. |
| Docker / docker-compose | Runs Langfuse's self-hosted stack (server + Postgres) locally for free, no paid observability SaaS needed. |
| Postgres | Backing database for self-hosted Langfuse — stores traces, not application data. |

### Backend

| Tool | Use |
|---|---|
| FastAPI | Exposes the pipeline as HTTP endpoints (`/incidents/simulate`, `/incidents/{id}/approve`, etc.) so the frontend can trigger and interact with incidents. Chosen over Flask/Django for native async support (LLM calls are I/O-bound) and automatic OpenAPI docs. |
| Uvicorn | ASGI server that runs the FastAPI app. |

### Frontend

| Tool | Use |
|---|---|
| React + TypeScript | Dashboard UI — incident feed, agent trace timeline, and the approval panel (including the typed-confirmation flow for high-risk actions). |
| Vite | Build tool/dev server for the React app — fast local iteration. |

### Testing & code quality

| Tool | Use |
|---|---|
| pytest | Unit and guardrail tests — especially the "try to break it" tests (malformed action proposals, prompt-injection attempts) that prove the guardrails actually hold. |
| ruff | Python linting/formatting — keeps the codebase consistent, signals attention to code quality. |

## 10. Success metrics (for the project itself)

- Diagnosis accuracy ≥ 80% on the golden set
- 100% of proposed fixes pass through the approval gate with zero bypass paths (verified by a dedicated guardrail test)
- Full trace available for 100% of simulated incidents
- Regression suite runs in CI and blocks a "prompt change" PR if eval scores regress beyond a defined threshold

## 11. Milestones

| Phase | Scope |
|---|---|
| 1 — Core pipeline | Monitor → Diagnosis → Remediation working end-to-end on hardcoded synthetic incidents |
| 2 — Guardrails | Approval gate, action schema validation, blast-radius classification |
| 3 — Evals | Golden set, eval harness, CI regression suite |
| 4 — Observability | Langfuse/OpenTelemetry tracing, cost/latency dashboard |
| 5 — UI | React dashboard: incident feed, trace viewer, approval flow |
| 6 — Postmortem loop | Postmortem agent + threshold feedback into Monitor agent |

## 12. Risks

- **Synthetic data realism:** if seeded incidents are too clean, evals won't be meaningful — invest real time in making the golden set genuinely varied and tricky
- **Scope creep:** the temptation to add more agent types — resist until phases 1-5 are solid
- **Demo depth vs. breadth:** a hiring manager will ask "walk me through a trace" — make sure the observability layer is genuinely functional, not just present
