---
date: 2026-03-08
patterns: [structured-output, tool-use, validate-after-generation]
project: Connections
---

# Reliable Structured Output from LLMs via Forced Tool Use

## Problem

LLMs responding with free text require fragile regex/JSON parsing that breaks when the
model adds explanation, wraps JSON in markdown fences, or changes format slightly.

## Why This Pattern Fits

The Anthropic API's `tool_choice={"type": "tool", "name": "..."}` forces the model to
call a specific named tool — guaranteeing a structured dict response. Combined with a
JSON Schema definition of the expected shape, this eliminates parsing entirely.

## Simplified Example (from `group_generator.py` and `puzzle_generator.py`)

```python
# Define the expected shape as a tool schema
_SEED_TOOL = {
    "name": "submit_seed",
    "input_schema": {
        "type": "object",
        "properties": {
            "seed_words": {"type": "array", "items": {"type": "string"}},
            "story":      {"type": "string"},
        },
        "required": ["seed_words", "story"],
    },
}

response = client.messages.create(
    model=MODEL,
    tools=[_SEED_TOOL],
    # This forces the model to call submit_seed — no plain-text fallback possible.
    tool_choice={"type": "tool", "name": "submit_seed"},
    messages=[{"role": "user", "content": prompt}],
)

# tool_block.input is already a Python dict — no JSON parsing needed.
tool_block = next(b for b in response.content if b.type == "tool_use")
result = tool_block.input  # {"seed_words": [...], "story": "..."}
```

## The "Validate After Generation" Companion Pattern

Forcing a tool call guarantees structure, but not semantic correctness. The pipeline
also validates Claude's selections in Python after the fact:

```python
# Claude selected categories by index — validate before trusting
unique_types = {c["category_type"] for c in selected}
if len(unique_types) < 2:
    # Swap last selected with a different-type candidate from the pool
    ...
```

This separation of concerns — LLM generates creatively, Python enforces hard rules —
is more robust than trying to encode every constraint into the prompt.

## Field Ordering Trick (from `group_generator.py`)

The schema in group_generator.py deliberately places `design_notes` *before* `words`
in the properties list. Claude fills tool parameters roughly in schema order, so this
forces it to commit its reasoning (rule + per-word verification) before writing the
word lists — preventing the failure mode of committing wrong words first.
