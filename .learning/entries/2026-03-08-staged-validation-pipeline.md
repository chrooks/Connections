---
date: 2026-03-08
patterns: [pipeline, short-circuit, fail-fast, cost-control]
project: Connections
---

## Problem

Puzzle validation requires three different checks of wildly different cost:
- Structural (free, instantaneous)
- Embedding model (free, ~200 ms, local)
- LLM (10 Claude API calls, ~$0.001)

Running all three unconditionally wastes money on puzzles that are already
structurally broken or semantically incoherent.

## Why a Staged Pipeline Fits

The checks form a natural total order by cost. Each stage is a necessary
(but not sufficient) condition for the next — a puzzle with duplicate words
can't pass embeddings, so there's no point sending it to the LLM. This
"cheapest gate first" ordering is a general pattern any time you have:

  - Multiple validations of increasing cost
  - Earlier failures are supersets of later failures
  - You want to minimize expected cost, not worst-case cost

## Key Implementation Detail

`validate_with_llm()` returns `passed` / `auto_fail_reasons` but no numeric
score. The pipeline derives one from `agreement_rate` in `solver_consistency`
(how often Haiku fully solved the puzzle across 8 attempts at temp=0.5):

```python
def _derive_llm_score(llm_report: dict) -> float:
    agreement_rate = llm_report["solver_consistency"]["agreement_rate"]
    assessment = llm_report["difficulty_assessment"]["assessment"]

    base = min(agreement_rate, 0.85)   # cap — >0.85 is the trivially-easy zone
    if assessment == "hard_or_flawed":
        base = max(0.0, base - 0.15)
    return round(base, 4)
```

The cap at 0.85 matters: 90%+ agreement normally triggers an auto-fail
("too easy"), so letting it produce a high score would be misleading.

## Final Scoring

```python
combined = (embedding_score * 0.4) + (llm_score * 0.6)
passed = not any(auto_fail_reasons) and combined > 0.6
```

LLM gets 60% weight because it catches logical ambiguity that embeddings
cannot see (e.g. two groups where both groupings are semantically valid).
