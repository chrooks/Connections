# Generation Pipeline Codemap

**Last Updated:** 2026-03-12
**Entry Points:** `backend/src/generation/puzzle_generator.py`, `backend/src/generation/batch_generator.py`, `backend/src/workers/worker.py`
**Dependencies:** Anthropic API, Supabase, sentence-transformers (embeddings), scikit-learn (metrics)

## Pipeline Architecture

```
Admin triggers /admin/generate-puzzles { count: N, config_name: "classic" }
  ↓
Routes writes puzzle_generation_jobs rows (status=queued)
  ↓
Worker polls for queued jobs (optimistic lock)
  ↓
generate_puzzle() — Multi-Step Quality Path
  ├─ Step 1: Diversity Seed (temp=1.0) — Claude
  ├─ Step 2: Category Brainstorm (temp=0.9) — Claude
  ├─ Step 3: Iterative Groups (varies) — Claude per group
  ├─ Step 3.5: Embedding Analysis (free) — Sentence Transformers
  ├─ Step 4: Red Herring Refinement (temp=0.7) — Claude
  └─ Step 5: Package into puzzle_data dict
  ↓
validation_pipeline() — Quality Gate
  ├─ embedding_validator — Similarity checks
  ├─ llm_validator — Quality review
  └─ Generates validation_score (0-100) + report
  ↓
seed_puzzle_to_pool() — Draft to Pool
  ├─ If score >= threshold: mark approved
  └─ Else: mark rejected (human can override)
  ↓
Update job row (status=completed/failed)
Update usage_tracker with costs

Alternative: batch_generator.py (Nightly Fills)
  ├─ Submit N single-shot requests via Batch API
  ├─ Poll for completion (30-60 min)
  └─ Validate & seed all at once
```

## Worker Pipeline (`puzzle_generator.py`)

### Architecture

**Quality Path:** Multi-step iterative generation with prompt caching

**Key File:** `backend/src/generation/puzzle_generator.py`

```python
def generate_puzzle(config_dict) -> dict | None:
    """
    Generate a full 4-group puzzle via multi-step pipeline.
    Returns {"groups": [...], "generation_metadata": {...}}
    """
    # 1. Diversity Seed
    # 2. Category Brainstorm
    # 3. Iterative Groups (calls generate_single_group per category)
    # 3.5 Embedding Bridge Analysis
    # 4. Red Herring Refinement
    # 5. Package & return
```

### Step 1: Diversity Seed (temp=1.0)

**Purpose:** Prevent thematic repetition across puzzle runs

**Prompt:** Seed 4 random domains (history, nature, food, tech) + creative story

**Output:** Context string for brainstorm step

**Cost:** ~300 input + 100 output tokens
**Caching:** System prompt + tool schema cached (first call)

### Step 2: Category Brainstorm (temp=0.9)

**Purpose:** Generate 6-8 candidate themes, score & select best 4

**Input:** Diversity seed from Step 1

**Prompt Assembly:**
```python
system_prompt = "You are an expert Connections puzzle designer..."
messages = [
    {
        "role": "user",
        "content": f"Given diversity seed: {seed}, generate 8 category ideas..."
    }
]
response = client.messages.create(
    model=MODEL,
    max_tokens=2048,
    temperature=0.9,
    system=[
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"}  # Cached
        }
    ],
    tools=[...],  # JSON tool schema, cached
    messages=messages,
)
```

**Output:** JSON array of {category, description, difficulty, explanation}

**Scoring:** Parse & rank by clarity + difficulty fit

**Cost:** ~500 input + 300 output tokens
**Caching:** Reuses system + tool schema from Step 1 (90% discount)

### Step 3: Iterative Group Building

**Purpose:** Generate 4 words per category with difficulty profile

**Key File:** `backend/src/generation/group_generator.py`

```python
def generate_single_group(
    category: str,
    difficulty: str,
    attempt: int = 1,
) -> dict | None:
    """Generate 4 words for a category with retry logic."""
    # Prompt Claude to generate 4 words + rationale
    # Parse JSON response
    # Validate: no duplicates, coherence
    # On fail: retry with refined prompt (up to 3 attempts)
```

**Per Group Cost:** ~250 input + 200 output tokens
**Total (4 groups):** ~1000 input + 800 output tokens

**Retry Logic:**
- Attempt 1: Generate 4 words + rationale
- Attempt 2 (fail): Regenerate with critique
- Attempt 3 (fail): Return best attempt or None

**CATEGORY_TYPES:** Enum of valid category types
- `WORDPLAY` — Puns, homophones
- `COMPOUND` — Phrases sharing word (e.g., "solar_system", "solar_panel")
- `SEMANTIC` — Synonyms, related words
- `CULTURAL` — Movies, TV, people, books
- `SPATIAL` — Countries, cities, regions

### Step 3.5: Embedding Bridge Analysis (Free)

**Purpose:** Identify "bridge words" (sit between groups in semantic space)

**Key File:** `backend/src/services/embedding_validator.py`

```python
def embedding_validator(puzzle_data) -> dict:
    """
    Compute embeddings for all 16 words.
    Check:
    - Within-group cosine similarity < 0.7 (too similar = boring)
    - Between-group similarity > 0.8 (should be distinct)

    Return: {"bridge_words": [...], "score": 0-100}
    """
    model = SentenceTransformer("all-mpnet-base-v2")
    embeddings = model.encode(all_16_words)

    # Compute pairwise similarities
    # Flag words with high similarity to other groups
    # Return bridge word indices
```

**No API Cost** (local embedding model)

**Output:** List of bridge word indices (prioritize for replacement in Step 4)

### Step 4: Red Herring Refinement (temp=0.7)

**Purpose:** Maximize misdirection, improve difficulty

**Strategy:**
1. Identify bridge words from Step 3.5
2. Prompt Claude to replace bridge words with stronger misdirections
3. Keep category membership clear

**Prompt:**
```
Given puzzle with bridge words: [indices]
Replace bridge words to maximize misdirection while keeping
categories clear. Return updated puzzle JSON.
```

**Temperature:** 0.7 (lower = more focused, less creative)

**Cost:** ~600 input + 400 output tokens

### Step 5: Final Assembly

**Purpose:** Package into puzzle_data dict for seeding

**Output Structure:**
```python
{
    "config_id": "uuid",
    "groups": [
        {
            "category": "Solar System Objects",
            "difficulty": "easy",
            "category_type": "SEMANTIC",
            "words": ["MOON", "STAR", "PLANET", "COMET"],
            "hint": "Celestial bodies"
        },
        # ... 3 more groups
    ],
    "generation_metadata": {
        "model": "claude-sonnet-4-5-20250929",
        "pipeline_version": "multi-step-v1",
        "total_input_tokens": 2500,
        "total_output_tokens": 1000,
        "api_calls": 5,
        "duration_seconds": 45,
        "cached_tokens": 2000
    }
}
```

## Validation Pipeline (`validation_pipeline.py`)

### Purpose

**Quality Gate** before puzzle enters approved pool

**Flow:**
```
puzzle_data (draft)
  ↓
embedding_validator() — Similarity checks
  ↓
llm_validator() — LLM review of difficulty & clarity
  ↓
Calculate combined score (0-100)
  ↓
If score >= threshold (default 70):
  seed_puzzle_to_pool(status=approved)
Else:
  seed_puzzle_to_pool(status=rejected, report=...)
```

### Embedding Validator

**Checks:**

1. **Within-Group Coherence** (cosine similarity)
   - Each word vs other words in same group
   - Should be moderate (not too similar, not too random)
   - Threshold: < 0.7

2. **Between-Group Distinctness**
   - Words in group A vs group B
   - Should be different
   - Threshold: > 0.8 (high distance)

3. **Category Type Validation**
   - Wordplay: check for letter patterns
   - Compound: ensure shared word is clear
   - Semantic: verify synonymy
   - Cultural: check factual accuracy

**Outputs:**
- `similarity_matrix` — 16x16 cosine matrix
- `within_group_scores` — avg similarity per group
- `between_group_scores` — min/max/avg distance
- `violations` — list of flagged word pairs
- `score` — 0-100 similarity validation score

### LLM Validator

**Purpose:** Quality review (difficulty, connection clarity, misdirection)

**Prompt:**
```
Review this Connections puzzle for quality:
Groups: [...]

Rate (0-100) on:
1. Connection clarity (groups are unambiguous)
2. Difficulty balance (not too easy, not unsolvable)
3. Misdirection (red herrings are believable)
4. Word appropriateness (no obscure words)

Return JSON: {"score": N, "reasoning": "...", "issues": [...]}
```

**Outputs:**
- `score` — 0-100 quality score
- `reasoning` — Explanation
- `issues` — List of flagged problems
- `difficulty_estimate` — easy/medium/hard/expert

### Combined Scoring

```python
def validate(puzzle_data) -> dict:
    embedding_score = embedding_validator(puzzle_data)["score"]
    llm_score = llm_validator(puzzle_data)["score"]

    combined = 0.6 * embedding_score + 0.4 * llm_score

    return {
        "validation_score": combined,
        "embedding_score": embedding_score,
        "llm_score": llm_score,
        "passed": combined >= 70,  # threshold
        "report": {...}
    }
```

**Threshold:** 70 (configurable)

## Batch Generator (`batch_generator.py`)

### Purpose

**Volume Path:** Cost-optimized bulk generation via Anthropic Batch API

**Use Case:** Nightly fills, restocking puzzle pool

### Workflow

```
1. Build N single-shot prompts (one per puzzle)
   - Each prompt is self-contained (no multi-step)
   - Simpler than worker pipeline

2. Submit via Anthropic Batch API:
   curl https://api.anthropic.com/v1/messages/batch \
     -H "anthropic-version: 2023-06-01" \
     -H "content-type: application/json" \
     -d @batch_request.json

3. Batch API processes overnight (50% cost discount)

4. Poll for completion status

5. On completion, validate all results

6. seed_puzzle_to_pool() for approved puzzles
```

### Cost Comparison

| Path | Cost/Puzzle | Quality | Latency | Use Case |
|------|-----------|---------|---------|----------|
| Worker | ~$0.05 | High | 5-30 min | On-demand, admin triggers |
| Batch | ~$0.015 | Lower | 15-60 min | Overnight bulk |

**Batch is 3x cheaper but lower quality (single-shot)**

### Implementation

```python
def run_batch_fill(count: int) -> dict:
    """
    Generate `count` puzzles via Batch API.
    Blocks until complete (check poll status in loop).
    """
    # 1. Build batch request (N messages)
    requests = [
        {
            "custom_id": f"puzzle-{i}",
            "params": {
                "model": "claude-opus",
                "messages": [{"role": "user", "content": single_shot_prompt}],
            }
        }
        for i in range(count)
    ]

    # 2. Submit batch
    batch_id = submit_batch(requests)

    # 3. Poll until DONE
    while True:
        status = get_batch_status(batch_id)
        if status == "DONE":
            break
        time.sleep(30)

    # 4. Fetch results
    results = get_batch_results(batch_id)

    # 5. Validate & seed
    for result in results:
        puzzle = parse_response(result)
        validation = validate(puzzle)
        if validation["passed"]:
            seed_puzzle_to_pool(puzzle, status="approved")
```

## Cost Tracking (`usage_tracker.py`)

### Purpose

**Append-only audit trail** of all Claude API calls

**Tracks:**
- Model name (claude-sonnet, claude-opus)
- Input tokens, output tokens
- Estimated USD cost
- Source (puzzle_generator, batch_generator, llm_validator)
- Puzzle ID (if applicable)
- Timestamp

### Usage

```python
from src.services.usage_tracker import log_api_call, get_cost_summary

# Log a call (done automatically in puzzle_generator)
log_api_call(
    model="claude-sonnet-4-5-20250929",
    input_tokens=2500,
    output_tokens=1000,
    source="puzzle_generator",
    puzzle_id="uuid-123"
)

# Query costs
summary = get_cost_summary(start_date="2026-03-01", end_date="2026-03-12")
print(f"Total: ${summary['total_cost_usd']}")
print(f"Calls: {summary['row_count']}")
print(f"Avg per puzzle: ${summary['avg_cost']}")
```

### Database Table

```sql
CREATE TABLE api_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model TEXT NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    cost_usd DECIMAL(10, 6),
    source TEXT,  -- puzzle_generator, batch_generator, llm_validator
    puzzle_id UUID REFERENCES puzzles(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Worker Lifecycle

**Key File:** `backend/src/workers/worker.py`

### Polling

```python
def worker_loop():
    while True:
        # 1. Query for queued jobs
        jobs = supabase.table("puzzle_generation_jobs") \
            .select("id, config_id") \
            .eq("status", "queued") \
            .limit(1) \
            .execute()

        if not jobs.data:
            time.sleep(5)  # No work, sleep
            continue

        job_id = jobs.data[0]["id"]
        config_id = jobs.data[0]["config_id"]

        # 2. Try to claim (optimistic lock)
        updated = supabase.table("puzzle_generation_jobs") \
            .update({"status": "processing"}) \
            .eq("id", job_id) \
            .eq("status", "queued") \
            .execute()

        if not updated.data:
            continue  # Lost race, try next job

        # 3. Process
        try:
            puzzle = generate_puzzle(config_dict)
            validation = validate(puzzle)
            puzzle_id = seed_puzzle_to_pool(puzzle, validation)
            status = "completed"
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            status = "failed"

        # 4. Update job
        supabase.table("puzzle_generation_jobs") \
            .update({"status": status}) \
            .eq("id", job_id) \
            .execute()
```

### Pool Monitor

**Key File:** `backend/src/workers/pool_monitor.py`

```python
def monitor_loop():
    while True:
        stats = get_pool_stats("classic")
        approved_count = stats["approved"]

        if approved_count < 10:
            # Queue replenishment jobs
            needed = 30 - approved_count
            for _ in range(needed):
                supabase.table("puzzle_generation_jobs").insert({
                    "config_id": config_id,
                    "status": "queued"
                }).execute()
            logger.info(f"Queued {needed} replenishment jobs")

        time.sleep(30)  # Check every 30s
```

## Common Tasks

### Triggering Puzzle Generation

```bash
curl -X POST http://localhost:5000/admin/generate-puzzles \
  -H "Content-Type: application/json" \
  -d '{"count": 10, "config_name": "classic"}'
```

### Monitoring Generation Quality

```python
from backend.src.services.usage_tracker import get_cost_summary

# Cost per puzzle
summary = get_cost_summary(start_date="2026-03-01")
cost_per = summary['total_cost_usd'] / summary['row_count']
print(f"${cost_per:.3f} per puzzle")

# Query validation scores
from supabase import create_client
client = create_client(url, key)
puzzles = client.table("puzzles") \
    .select("id, validation_score, status") \
    .gte("validation_score", 70) \
    .execute()
print(f"{len(puzzles.data)} approved puzzles")
```

### Debugging a Failed Puzzle

```python
# Check job status
job = supabase.table("puzzle_generation_jobs") \
    .select("*") \
    .eq("id", "job-uuid") \
    .single() \
    .execute()

# Check puzzle validation
puzzle = supabase.table("puzzles") \
    .select("id, validation_score, validation_report, status") \
    .eq("id", "puzzle-uuid") \
    .single() \
    .execute()

print(puzzle.data["validation_report"])  # Reason for rejection
```

### Adjusting Quality Thresholds

**In `validation_pipeline.py`:**
```python
VALIDATION_THRESHOLD = 70  # Increase to 75 for stricter quality
```

**In `puzzle_generator.py`:**
```python
# Temperatures control creativity vs focus
DIVERSITY_SEED_TEMP = 1.0  # High: diverse ideas
BRAINSTORM_TEMP = 0.9      # Medium-high: many candidates
REFINEMENT_TEMP = 0.7      # Lower: focused improvements
```

## External Dependencies

- `anthropic@0.28+` — Claude API, Batch API
- `supabase@2.x` — Puzzle pool, job queue
- `sentence-transformers@2.x` — Embedding validation
- `scikit-learn` — Cosine similarity metrics
- `torch` — Embedding model backend

---

**See also:** [Backend Codemap](backend.md), [Database Schema](database.md), [API Reference](api.md)
