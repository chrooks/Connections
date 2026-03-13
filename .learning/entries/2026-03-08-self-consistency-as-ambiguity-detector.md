---
date: 2026-03-08
patterns: [self-consistency, llm-evaluation, multi-shot-sampling, validation-pipeline]
project: Connections
---

# Self-Consistency Sampling as an Ambiguity Detector

## Problem being solved

A Connections puzzle can fail in two different ways that look identical from the outside:
1. **Too hard** — the intended grouping is non-obvious, so solvers can't find it.
2. **Ambiguous** — multiple valid groupings exist, so solvers each find a *different* valid one.

A single solve attempt can't distinguish these cases. If the model fails, you don't know why.

## Why self-consistency sampling fits

Running the same solver N times at temperature > 0 and aggregating the results reveals the *distribution* of solutions the model finds. This distribution tells you:

- **High agreement + correct** → puzzle is easy (maybe too easy)
- **High agreement + wrong** → puzzle is hard but unambiguous (model consistently picks a wrong-but-consistent interpretation)
- **Low agreement** → either genuinely hard OR ambiguous (multiple valid groupings exist)

The devil's advocate check resolves the low-agreement ambiguity: if the LLM can *articulate* a valid alternative when shown the intended solution, it's ambiguous; if it can't, it's just hard.

## Relevant code from llm_validator.py

```python
# Each attempt shuffles word order independently — prevents the model from
# exploiting positional patterns across runs
for _ in range(num_attempts):
    shuffled = all_words.copy()
    random.shuffle(shuffled)
    proposed = solve_puzzle_attempt(
        puzzle_words=shuffled, temperature=temperature, tracker=tracker
    )
    all_attempts.append(proposed)
    num_correct, per_group_matched = _score_attempt(proposed, connections)
    if num_correct == num_groups:
        correct_full_attempts += 1

agreement_rate = correct_full_attempts / num_attempts
```

## The schema field ordering trick

Placing `reasoning` before `groups` in the tool schema forces Claude to articulate
its grouping logic before committing word assignments — same idea as `design_notes`
first in `group_generator.py`. Because Claude fills tool parameters roughly in
schema order, this prevents the failure mode of picking groups and then rationalizing them.

```python
_SOLVE_TOOL = {
    "input_schema": {
        "properties": {
            "reasoning": {...},   # ← filled first: forces step-by-step logic
            "groups": {...},      # ← filled second: commits only after reasoning
        }
    }
}
```

## Auto-fail logic

Three conditions trigger automatic rejection:
1. `agreement_rate > 0.9 AND difficulty == "too_easy"` — trivially solvable
2. `devils_advocate.found_alternative == True` — genuinely ambiguous
3. `agreement_rate < 0.1` — unsolvable or deeply flawed
