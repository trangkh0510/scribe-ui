# Scribe

> *clean-transcript-to-report*

### From raw transcript → a report you can actually use. Not "paste it into ChatGPT and pray."

You just wrapped a user interview, a meeting, or a support call. What you have is a recording full of
timestamps, repeated speaker names, "um"s and "uh"s, speech-recognition errors, half-finished
sentences. The usual move: dump the whole blob into a chatbot and get back a generic summary — vague,
embellished with invented details, and **impossible to trace back to anything the person actually said.**

**Scribe does it differently.** Two steps, one pipeline, one container:

> **1. Clean** — a disciplined *rule engine* scrubs the transcript in the background.
> **2. Analyze** — turns the clean transcript into a structured HTML report where **every conclusion is backed by a quote.**

---

## Why it's worth it (3 differentiators)

### 🧹 1. A 9-stage rule engine cleans the transcript — not "hey AI, fix this for me"

The Clean step doesn't just hand the raw transcript to an LLM and hope. It runs through a **9-stage
pipeline purpose-built for Vietnamese transcripts** (with English code-switching and southern-accent
speech), governed by one backbone principle — **Precision > Recall: better to miss an error than to
"correct" a word that was already right:**

| Stage | What the engine does |
|---|---|
| **Token Locking** | Hard-locks phone numbers, OTPs, transaction IDs, money amounts, calendar years — so they can **never be mangled** by a later rule |
| **ASR & Brand** | Fixes heavy recognition errors, normalizes brands ("Tóp Tóp" → TikTok), repairs code-switching ("vau chờ" → voucher) |
| **Southern accent** | Detects the accent region → enables a dedicated ruleset ("dzậy" → vậy), while **keeping valid dialect words** (tui, ổng, mắc) because those are valuable demographic signal for UX |
| **Numbers & money** | Distinguishes "year 2023" from "5 million", normalizes "1 5 triệu" → "one and a half million", decodes slang ("một củ" = 1,000,000đ) |
| **Filler & self-correction** | Strips "um, uh, like, you know", collapses stutters ("I I I" → "I"), keeps polite particles |
| **Sentences, names, QA** | Adds punctuation only when confident, capitalizes names via a whitelist, and **flags uncertain spots for human review** instead of guessing |

You **toggle each rule on/off** and add your own. Whatever the engine isn't sure about, it **flags
rather than fabricates** — and you review and hand-edit before anything reaches analysis.

### 🧠 2. Transcript → report logic: structured, evidence-backed, drift-free

The Analyze step does **not** return a paragraph of prose. It runs a controlled pipeline:

```
gate (gatekeeper) → analyze (LLM returns JSON) → validate (schema) → render (HTML)
```

- **The gate blocks before you spend a cent:** it requires **objectives** (your goals / research
  questions), exactly 1 file, and a minimum length — checked **before any LLM call** so you never burn
  quota on garbage.
- **Every finding carries evidence:** each insight / pain point ships with a **verbatim ≤15-word quote**
  pulled straight from the transcript. No "the AI said so" — you can trace it back to the exact sentence.
- **Schema enforces discipline:** the LLM must return JSON matching a strict schema (validated with
  Pydantic); a mismatch triggers a retry. The HTML report is **rendered deterministically in Python**
  from clean JSON — the model never gets to "paint" the layout however it feels.

### 🎯 3. Tailored per use case — not one template for everything

Not every report is the same. Each type has its own **brain prompt + schema + rendering**, asking the
exact questions that role needs answered:

| Type | For | What you get back |
|---|---|---|
| **`ux`** | UX researcher | Findings + **severity-tagged pain points (high/med/low)** mapped to flows, quotes, pass/fail verdict, scorecard, suggestions |
| **`cs`** | CS / operations | Summary + **customer sentiment trajectory per phase**, issues ranked by severity, action items, verdict |
| **`meeting`** | PM / lead / note-taker | **Decisions (who made them)** + action items (task · owner · deadline) + off-topic list + verdict |

---

## Up and running in 3 minutes

Open the endpoint → a single-page, two-step wizard:

1. **Clean** — upload `.vtt` (Teams) / `.docx` / `.txt` → toggle rules → clean → **review & hand-edit**.
2. **Analyze** — pick `cs` / `ux` / `meeting` → enter **objectives** → get an **HTML report**.

---

## Limitations (straight talk)

- **One file per analysis** for now. Got multiple transcripts? Combine them into a single file first.
- **Objectives are required** for Analyze — no goals, the gate blocks you (by design: a report with no
  objective is a useless report).
- The cleaning rule engine is tuned for **Vietnamese transcripts** (with code-switching + southern accent).

---

## Related docs

| File | Content |
|---|---|
| `docs/01-agent-README.md` | Architecture, analysis pipeline, detailed run/deploy |
| `docs/02-clean-pipeline-9-rules.md` | **Full 9-stage spec of the cleaning rule engine** |
| `docs/prompts/{cs,ux,meeting}.md` | Brain prompt for each report type |
| `HANDOVER.md` · `DEPLOY.md` | Handover + security · build/push image + create runtime |
