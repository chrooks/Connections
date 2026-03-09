# Phase 6: Validation Pipeline — Session Summary

## What Was Built

### New: `backend/src/services/validation_pipeline.py`

Orchestrates the two existing validators (embedding + LLM) into a single
3-stage pipeline with short-circuit logic to avoid unnecessary API costs.

**`validate_puzzle(puzzle_data)`** — the main entry point:

| Stage | Cost | What it checks | Fails fast? |
|-------|------|----------------|-------------|
| 1 — Structural | Free | Group/word count, duplicates, sentence-length phrases, distinct category names | Yes — no API calls wasted |
| 2 — Embedding | Free (local model) | Semantic coherence, group separation, bridge words, clustering ARI | Yes — skips LLM if already failed |
| 3 — LLM | ~10 API calls | Solvability (8 attempts), ambiguity (devil's advocate), difficulty calibration | Final gate |

Final score = `embedding × 40% + LLM × 60%`. Passes if no auto-fails and score > 0.6.

**`validate_and_store(puzzle_id, supabase_client)`** — full DB lifecycle:
fetches a draft puzzle, runs the pipeline, then calls `approve_puzzle()` or
`reject_puzzle()` from `puzzle_pool_service.py`.

**`__main__`** — generates a puzzle via `puzzle_generator.generate_puzzle()`,
validates it, prints results to console, and writes a timestamped JSON to
`backend/validation_runs/`.

---

## Calibration Fix Applied During Testing

**Problem:** The initial `_derive_llm_score()` used `agreement_rate` directly
as a quality score — e.g. 25% agreement → 0.25 score. This treated puzzle
difficulty as poor quality, which is backwards. A puzzle Haiku solves 25% of
the time is appropriately challenging, not broken.

**Fix:** Changed to a binary-style approach. The LLM stage is primarily a
gate — its auto-fail rules already handle the bad extremes. Anything that
clears those gates gets a high base score:

```
passed, appropriate   → 0.75
passed, too_easy      → 0.70  (borderline, minor penalty)
passed, hard_or_flawed → 0.55  (0 correct at temp=0 — structurally suspect)
auto-fail triggered   → 0.0
```

---

## Generator Change: Domain Diversity (Lever 1)

**File:** `backend/src/generation/puzzle_generator.py` — `_step2_category_brainstorm()`

Added a 5th selection rule to the Step 2 prompt:

> The selected categories must span at least 3 distinct knowledge domains
> (sport, music, food, science, language, history, geography, pop culture,
> nature, technology, art, literature). Two categories from the same narrow
> semantic space cause word-level ambiguity that hurts embedding separation.

**Why this matters:** Low embedding separation scores were traced to the
generator picking categories from adjacent semantic neighbourhoods (e.g.
"Types of fabric" + "Types of paint finish" both live in the "surface
quality/texture" corner of embedding space). This is a prompt-only change —
no Python enforcement yet.

---

## What Was Considered But Not Implemented

**Lever 2 — Word specificity constraint in `group_generator.py`:**
Rejected. Adding "prefer narrow-meaning words" to the word-selection prompt
would make puzzles too easy — this was a known problem from the original
generation work.

**Lever 3 — Embedding feedback loop between Step 3 and Step 4:**
Kept in reserve. The idea: run the embedding validator after Step 3 builds
groups, identify bridge words, and pass them to Step 4 with instructions to
prioritise replacing those specific words. Adds one extra embedding call per
generation but gives Step 4 concrete data rather than asking Claude to guess.

---

## Open Questions / Next Steps

- Run more samples (10+) with Lever 1 active to see if embedding scores improve
- If separation is still low, consider Lever 3 (embedding feedback loop)
- `PASSING_SCORE_THRESHOLD = 0.6` may need revisiting once more data exists —
  the current runs (all failing) don't yet tell us what a "good" puzzle scores
- `validation_runs/*.json` files accumulate with each run — add to `.gitignore`
  once the calibration work is done

---

## Key Files

| File | Role |
|------|------|
| `backend/src/services/validation_pipeline.py` | New — orchestration layer |
| `backend/src/services/embedding_validator.py` | Existing — Stage 2 |
| `backend/src/services/llm_validator.py` | Existing — Stage 3 |
| `backend/src/services/puzzle_pool_service.py` | Existing — approve/reject DB calls |
| `backend/src/generation/puzzle_generator.py` | Modified — domain diversity in Step 2 |
| `backend/validation_runs/` | New — timestamped JSON output from test runs |
