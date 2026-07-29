# UnifAI User Best Practices Guide

A practical guide for **end users** and **power users** on getting reliable results from UnifAI — especially **chat**, **workflows (blueprints)**, and **templates**.

> **Note:** Organization-specific workflow examples and approved prompt libraries can be added in [Your examples (add later)](#your-examples-add-later).

---

## 1. Mental model (what you are using)

UnifAI is built around a few concepts. Knowing them makes everything else clearer.

| Concept | What it means for you |
|--------|------------------------|
| **Workflow / blueprint** | A reusable agent graph: which agents run, in what order, with which tools, retrievers, and models. |
| **Chat / session** | A live run of a blueprint. You send messages; agents execute and stream results back. |
| **Template** | A pre-built blueprint with blanks (placeholders). Fill them in once to create a ready-to-use workflow. |
| **Inventory / resources** | Shared building blocks (LLMs, tools, providers, retrievers, etc.) that workflows attach to. |
| **Prompt shortcuts** | Up to three saved starter prompts on a blueprint — one click inserts them into chat. |

**Rule of thumb**

- Use a **template** when you want a known pattern quickly.
- Use the **workflow builder** when you need to customize agents, tools, or routing.
- Use **chat** to run and iterate — not to redesign the whole system every time.

---

## 2. Choosing the right path

| Goal | Start here |
|------|------------|
| Run something that already exists | **Chats** → pick the workflow → send a clear request |
| Create a standard workflow without designing from scratch | **Templates** → fill placeholders → materialize → open chat |
| Design or refine agent behavior, tools, or graph structure | **Agentic AI / workflow builder** |
| Reuse the same request often | Configure **prompt shortcuts** on that blueprint |

Prefer the simplest path that works. Do not rebuild a workflow for every one-off question if an existing chat + better prompt is enough.

---

## 3. Chat best practices

### 3.1 Before you send

1. **Pick the right workflow** — Match the job (e.g. knowledge search vs. tool-heavy automation). The wrong blueprint will ignore even a perfect prompt.
2. **One job per message** — Ask for a single outcome. Split multi-step jobs into follow-ups once you see intermediate results.
3. **State constraints early** — Audience, format, length, sources to prefer/avoid, and what “done” looks like.
4. **Give the context the agents cannot see** — Ticket IDs, product names, time ranges, file names, team names, success criteria.

### 3.2 While it runs

- Watch the **execution stream / graph** when results look wrong — identify which node failed or returned empty context.
- Prefer **follow-up refinement** over restarting from scratch: “Shorten to 5 bullets,” “Cite only internal docs,” “Redo step 2 with X.”
- If output is empty or generic, check whether the workflow has the right **retrievers/tools** attached before rewriting the prompt again.

### 3.3 After you get an answer

- Treat the first response as a draft when the task is high-stakes.
- Ask for verification: sources used, assumptions, and open questions.
- Save winning prompts as **prompt shortcuts** on that blueprint (max 3) so the team can reuse them.

### 3.4 Chat do’s and don’ts

| Do | Don’t |
|----|--------|
| Name the deliverable (“summary for execs,” “Jira-ready description”) | Ask vague “help with this” with no outcome |
| Bound scope (“last 30 days,” “only runbooks,” “P1 incidents”) | Dump unrelated context and hope the model sorts it |
| Ask for structure (“bullets + risks + next steps”) | Demand many unrelated outputs in one shot |
| Correct with specifics (“wrong product; use X”) | Restart a new session for every small tweak |

---

## 4. Prompting guide

Good prompts in UnifAI are specific about **role**, **task**, **context**, **constraints**, and **output shape**. Agents and tools still depend on what the blueprint can actually do.

### 4.1 Prompt checklist

Use this mental template:

```text
Role / intent: what you want the system to act as
Task: the single outcome
Context: facts the agents need (IDs, links, names, dates)
Constraints: sources, tone, length, what to exclude
Output: format and acceptance criteria
```

### 4.2 Weak vs strong prompts

**Weak**

```text
Look into the outage and tell me what happened.
```

**Strong**

```text
Summarize yesterday’s payment-service outage for an engineering standup.

Context:
- Service: payments-api
- Window: 2026-07-28 14:00–18:00 UTC
- Prefer internal docs and Slack incident channels over speculation

Output:
1. Timeline (5–8 bullets)
2. Likely root cause (with confidence)
3. Customer impact
4. Open follow-ups
If evidence is missing, say what is missing instead of guessing.
```

**Weak**

```text
Write something about onboarding.
```

**Strong**

```text
Draft a 1-page onboarding checklist for new UnifAI end users.

Audience: non-technical business users
Include: how to start a chat, how to pick a workflow, how to use a template
Exclude: admin setup, deployment, YAML editing
Format: numbered steps + a short “common mistakes” section at the end
```

**Weak**

```text
Fix my workflow.
```

**Strong (power user)**

```text
Review this blueprint’s behavior after my last run.

Observed issue: the final answer ignored Slack results and only used docs.
What I expected: a merged answer with both sources, noting conflicts.

Please:
1. Explain which node likely dropped Slack context
2. Suggest concrete config/prompt changes on the merger or Slack agent
3. Give me a better user prompt to retest
```

### 4.3 Prompt patterns that work well

**Clarify then act**

```text
Before answering, list the assumptions you need. If any critical assumption is missing, ask up to 3 questions. Otherwise proceed with the task below:
[task]
```

**Evidence-bound answer**

```text
Answer only from retrieved / tool results. If evidence is insufficient, say “insufficient evidence” and list what to fetch next. Do not invent citations.
```

**Format contract**

```text
Return exactly:
- Decision: Go / No-Go / Needs info
- Why (3 bullets max)
- Risks
- Next action owner
No preamble.
```

**Iteration prompt**

```text
Keep the structure of your previous answer. Only change: [specific correction]. Do not rewrite unrelated sections.
```

### 4.4 Prompt shortcuts (power users)

Use shortcuts for prompts you run often on the same blueprint:

- Keep each shortcut **self-contained** (context + format), not a one-word label.
- Prefer **role-based** shortcuts: “Exec summary,” “Incident timeline,” “Customer reply draft.”
- You can store up to **3** shortcuts per blueprint — make them the highest-value starters.
- Update them when the team’s real wording improves; stale shortcuts teach bad habits.

---

## 5. Workflows (blueprints) best practices

### 5.1 Design principles

1. **Name for the job** — `Incident Postmortem Assistant` beats `My Workflow 3`.
2. **Keep graphs readable** — Prefer a clear path over many optional branches until you need them.
3. **Give each agent one job** — Searcher, synthesizer, and formatter should not all be the same vague agent.
4. **Put instructions where they belong** — System/agent instructions define stable behavior; user chat prompts should carry the specific request.
5. **Validate before sharing** — Fix validation errors before teammates rely on the blueprint.
6. **Attach only needed tools/retrievers** — Extra tools increase noise, cost, and failure modes.

### 5.2 Building for good chat results

- Add an explicit **user input → agent work → final answer** path.
- If multiple sources are used, include a **merge/synthesize** step with instructions for conflicts and missing data.
- Write agent system messages that define:
  - what success looks like
  - what to do when tools return nothing
  - output format expectations
- Configure **prompt shortcuts** for the 1–3 most common entry points.

### 5.3 Testing a workflow

1. Materialize or save the blueprint.
2. Open a chat session on it.
3. Run **one happy-path prompt** (clear, constrained).
4. Run **one sparse prompt** (minimal context) to see failure behavior.
5. Run **one adversarial/edge prompt** (ambiguous ask, conflicting constraints).
6. Inspect node outputs when quality drops — fix the node/tool/config, not only the chat wording.

### 5.4 When to edit the workflow vs. the prompt

| Symptom | Usually fix |
|---------|-------------|
| Wrong tone/format for this one request | Chat prompt |
| Consistently ignores a source or tool | Workflow config / agent instructions / attachments |
| Always too long / unstructured | Agent system message or final-answer node instructions |
| Wrong model or missing tool capability | Inventory resource + blueprint wiring |
| Teammates ask the same thing differently | Prompt shortcuts + clearer blueprint description |

---

## 6. Templates best practices

Templates are the fastest way to create a correct workflow when a pattern already exists.

### 6.1 End-user flow

1. Open **Templates**.
2. Read the description and category — confirm it matches your job.
3. Fill every placeholder carefully (model, retriever, names, etc.).
4. Materialize into a blueprint (optionally rename it for your use case).
5. Start a chat and test with a strong first prompt.
6. Add prompt shortcuts once the workflow proves useful.

### 6.2 Filling placeholders well

| Do | Don’t |
|----|--------|
| Choose resources that match the template’s intent | Pick a random LLM/tool “just to proceed” |
| Use clear blueprint names after materialize | Leave generic default names if several copies will exist |
| Validate inputs before materializing when the UI offers it | Skip required fields and patch later under time pressure |

### 6.3 After materialize

- Treat the new blueprint as yours to refine — templates are starting points, not frozen law.
- If you change the graph heavily, update the name/description so others know it diverged.
- Share the refined blueprint (or contribute a better template later) instead of asking everyone to rebuild it.

---

## 7. Power-user playbook

### 7.1 Reliability habits

- Keep a small personal library of **tested prompts** per workflow.
- Prefer **narrow tools + clear instructions** over broad “do everything” agents.
- When collaborating in a team workspace, avoid editing a blueprint another person is actively changing (edit locks / busy state).
- For shared workflows, document in the description: purpose, expected inputs, and example prompts.

### 7.2 Debugging poor answers

Work top-down:

1. **Prompt clarity** — Was the ask ambiguous?
2. **Session/node stream** — Which node produced weak/empty output?
3. **Resources** — Is the retriever/tool/LLM the right one and healthy?
4. **Agent instructions** — Do system messages contradict the user ask?
5. **Graph structure** — Is merge/final-answer wired so earlier work can reach the user?

### 7.3 Collaboration tips

- Share blueprints that are validated and have at least one known-good prompt shortcut.
- Agree on output formats for recurring jobs (incident notes, exec updates, customer replies).
- Prefer improving one shared workflow over creating many near-duplicates.

---

## 8. Quick reference

### End users

- Pick the right workflow/template first.
- One clear job per message, with context and output format.
- Refine with follow-ups; save winners as shortcuts.

### Power users

- Design agents with single responsibilities.
- Validate graphs; attach only needed resources.
- Use templates to bootstrap, then tune instructions and shortcuts.
- Debug via execution stream before rewriting the whole blueprint.

---

## Your examples (add later)

Use this section for organization-approved content.

### Example workflows

<!-- Add: name, purpose, when to use, link/blueprint id, starter prompt -->

1. _TBD_
2. _TBD_

### Approved prompt library

<!-- Add: title, target workflow, full prompt text, expected output notes -->

#### Prompt: _TBD_

```text
Paste approved prompt here.
```

#### Prompt: _TBD_

```text
Paste approved prompt here.
```

---

## Glossary

| Term | Meaning |
|------|---------|
| Blueprint | Saved workflow definition (agent graph) |
| Session / chat | One execution conversation against a blueprint |
| Template | Parameterized blueprint factory |
| Materialize | Create a real blueprint (and resources) from a template |
| Prompt shortcut | Saved starter prompt on a blueprint (max 3) |
| Inventory | Catalog of reusable LLMs, tools, providers, retrievers, nodes |
| Retriever | Component that searches indexed knowledge (e.g. docs, Slack) |
