---
date: 2026-03-08
patterns: [pipeline, chain-of-responsibility, temperature-tuning]
project: Connections
---

# LLM Pipeline Pattern with Temperature Tuning per Step

## Problem

Calling an LLM once with a large prompt to generate a complex artifact (like a full puzzle)
tends to produce repetitive, low-quality output. A single prompt can't optimise for
creativity and analytical rigour simultaneously.

## Why This Pattern Fits

A **pipeline** breaks generation into discrete steps, each with a single responsibility
and its own temperature calibrated to its task:

- High temperature (1.0) → maximum variety for creative seeding
- Medium temperature (0.9) → creative but constrained for brainstorming
- Lower temperature (0.7) → analytical precision for refinement

Each step's output feeds the next as structured context, so later steps build on earlier
decisions rather than reinventing them.

## Simplified Example (from `puzzle_generator.py`)

```python
def generate_puzzle(config):
    client = anthropic.Anthropic(...)
    tracker = _TokenTracker()

    # Step 1: creative seed — high temp for variety
    seed = _step1_diversity_seed(client, tracker, theme_hint)   # temp=1.0

    # Step 2: brainstorm using seed story as context
    candidates, selected = _step2_category_brainstorm(          # temp=0.9
        client, tracker, seed["story"], seed["seed_words"], ...
    )

    # Step 3: build each group, passing prior groups as context
    groups = _step3_build_groups(tracker, selected, words_per_group)

    # Step 4: analytical refinement — lower temp for precision
    groups, analysis = _step4_red_herring_refinement(           # temp=0.7
        client, tracker, groups
    )

    return _step5_assemble(groups, seed["story"], ...)
```

## What Would Break With a Different Structure

A single mega-prompt can't vary temperature across tasks. Without the seed story as
context, category brainstorming would produce the same default themes every run
(seasons, primary colors, chess pieces). Without iterative group building, earlier
groups can't inform red herring planning for later ones.
