# Building an LLM-powered NYT Connections puzzle generator

**The most effective approach to generating high-quality Connections puzzles with Claude is a multi-step iterative pipeline — not a single prompt — combined with embedding-based validation and a pre-generated puzzle pool architecture.** This finding comes from the definitive academic research on the topic, "Making New Connections" (Merino et al., AAAI AIIDE 2024), which demonstrated that iterative generation produces puzzles human players rate as competitive with NYT's own in creativity and enjoyment. The system architecture should decouple generation entirely from serving, using background workers to maintain a pool of validated puzzles ready for instant delivery. Total cost per validated puzzle can be driven as low as **$0.005–$0.015** using Claude's prompt caching and batch APIs.

---

## The research proves iterative generation beats single-prompt approaches

The single most important finding across all research is that **one-shot puzzle generation fails**. The Merino et al. team at NYU's Game Innovation Lab found that asking an LLM to produce all 16 words at once yields inferior puzzles — less creative, less enjoyable, and often structurally broken. Their key insight: "The more rules we added, the more GPT seemed to ignore them." The breakthrough was decomposing generation into smaller, focused sub-tasks.

**The proven pipeline has three roles — Creator, Editor, and Validator** — executed across multiple LLM calls. The Creator generates one word group at a time, building iteratively on prior groups. The Editor refines category names and fixes errors. The Validator (a separate LLM call or human) checks solvability. In head-to-head user studies, this pipeline produced puzzles that beat NYT puzzles in **42.86%** of preference comparisons and tied in 14.29%.

### Recommended multi-step generation pipeline

**Step 1 — Category brainstorm (Claude Sonnet, temperature=0.9–1.0).** Generate 6–8 candidate category themes. To prevent repetitive outputs, use the paper's *diversity injection technique*: inject 4 randomly selected seed words from a curated word bank, ask Claude to write a brief creative story using them, then use the story as inspiration for categories. This dramatically increases thematic variety. Also rotate required category styles (synonyms, wordplay, fill-in-the-blank, knowledge-based, hidden patterns) to ensure diversity.

**Step 2 — Iterative word group building (Claude Sonnet, temperature=0.8–1.0).** Generate one group at a time, providing all previously generated groups as context. For each group, generate a pool of **8 candidate words** (not just 4) — this gives flexibility for later selection and difficulty calibration. Critically, instruct Claude that "at least one word in this new group should plausibly fit into one of the existing groups" to create intentional overlap.

**Step 3 — Red herring injection and refinement (Claude Sonnet, temperature=0.7).** Given all groups, ask Claude to identify existing cross-group tensions and suggest word swaps that increase red herring potential. The paper found two mechanisms: *intentional overlaps* (words that plausibly belong to multiple categories, like "fudge" fitting both PHOOEY! and SUNDAE TOPPINGS) and *false groups* (tempting but incorrect groupings across categories, like multiple rodent-related words scattered across groups).

**Step 4 — Validation pass (Claude Haiku, temperature=0).** A cheaper model verifies structural constraints, attempts to solve the puzzle, and flags issues. More on this below.

**Step 5 — Difficulty assignment (Claude Haiku, temperature=0).** Assign yellow/green/blue/purple rankings based on category abstractness and word-group semantic distance.

### Prompt engineering specifics for Claude

Use **Claude's structured outputs** (the `output_format` parameter with JSON schema) to guarantee valid puzzle JSON. This uses constrained decoding compiled into a grammar — no parsing failures, ever. The first request with a new schema has slight extra latency for grammar compilation, but compiled grammars are cached for 24 hours. Here's the recommended schema:

```json
{
  "type": "object",
  "properties": {
    "groups": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "difficulty": {"type": "string", "enum": ["yellow", "green", "blue", "purple"]},
          "category_name": {"type": "string"},
          "words": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
          "red_herring_connections": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["difficulty", "category_name", "words"]
      }
    },
    "design_notes": {"type": "string"}
  }
}
```

For the creative generation steps, use **extended thinking** (available on Sonnet 4.5 and newer) — letting Claude reason internally before producing the puzzle improves category creativity. Set a minimum budget of 1,024 thinking tokens. For system prompts, include explicit design principles: categories must be more specific than generic labels, category name words can't appear in the category, mix at least two category styles per puzzle, and every puzzle needs at least one false group opportunity.

**Few-shot examples are strongly recommended.** Include 2–3 complete example puzzles (ideally real NYT puzzles or high-quality generated ones) showing the target format, difficulty gradient, and red herring patterns. With prompt caching enabled, including 10–20 examples costs almost nothing after the first call.

---

## A 10-stage validation pipeline ensures puzzle quality

Validation is where most puzzle generators fail. A word puzzle can be structurally valid but unfair, trivially easy, or ambiguous. The recommended pipeline combines programmatic checks, embedding-based analysis, and LLM solver agents.

### Embedding-based validation using MPNet

The **all-mpnet-base-v2** model from the `sentence-transformers` library is the empirically validated choice for Connections puzzle analysis. Research by Todd et al. (2024) and Merino et al. (2024) established clear cosine similarity thresholds that map to difficulty levels:

| Difficulty | Avg. intra-group cosine similarity | Interpretation |
|---|---|---|
| Yellow (easiest) | **0.28–0.32** | Words are obviously related |
| Green | 0.22–0.28 | Requires some thought |
| Blue | 0.18–0.22 | Non-obvious connections |
| Purple (hardest) | **0.12–0.18** | Lateral thinking required |

For red herring effectiveness, **false groups need cross-group similarity ≥ 0.43** to successfully misdirect players. Below that threshold, players weren't tricked. Between-group similarity above 0.60 signals ambiguity — words may legitimately belong to multiple groups.

The core validation checks in Python:

```python
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-mpnet-base-v2')

def validate_puzzle(groups):
    all_words = [w for g in groups for w in g['words']]
    embeddings = model.encode(all_words)
    
    # 1. Within-group coherence
    for group in groups:
        group_embs = model.encode(group['words'])
        sim = util.cos_sim(group_embs, group_embs)
        coherence = (sim.sum() - len(group['words'])) / (len(group['words']) * (len(group['words']) - 1))
        # Check against difficulty thresholds
    
    # 2. Between-group distinctiveness (ratio should be > 1.5)
    # 3. Bridge word detection (flag if cross-group sim > 80% of own-group sim)
    # 4. Clustering recovery (constrained k-means should find intended groups)
```

### LLM solver validation

Run **self-consistency checking**: generate 10+ solution attempts at temperature > 0 and check if the majority finds the intended grouping. If solutions diverge significantly, the puzzle is ambiguous. Additionally, use a **"devil's advocate" prompt** — ask Claude to find alternative valid groupings. If it finds a plausible one, the puzzle has an ambiguity problem.

A practical difficulty calibration: if **Haiku solves the puzzle instantly**, it's too easy. If Haiku gets 2–3 groups right, difficulty is appropriate. If Haiku gets 0–1 groups, the puzzle may be too hard or poorly constructed.

### Complete validation stage sequence

The full pipeline runs: structural validation (16 unique words, 4 groups of 4) → content safety check → within-group coherence via embeddings → between-group distinctiveness → bridge word detection → constrained k-means clustering recovery → difficulty distribution check → LLM solver with self-consistency → devil's advocate uniqueness check → LLM quality judge (category creativity, theme variety). Each stage produces a score that feeds into a composite quality metric. Only puzzles scoring above threshold get published.

---

## Architecture: pre-generated pool with event-driven replenishment

### Why pre-generation is non-negotiable

Claude API latency of **3–10+ seconds per call** — multiplied across a multi-step pipeline — makes on-demand generation unacceptable for user-facing requests. The correct pattern is a constantly replenished pool of validated puzzles served instantly from a database, with background workers asynchronously generating replacements.

### Recommended tech stack

| Component | Technology | Rationale |
|---|---|---|
| Frontend | **Vite + React + TypeScript** | SPA-optimized, fast dev cycle, same language as backend |
| UI/Styling | **Tailwind CSS + shadcn/ui** | Proven in existing Connections clones |
| Animations | **Motion (Framer Motion)** | `LayoutGroup` and `AnimatePresence` are purpose-built for tile reordering/reveals |
| State management | **Zustand** (or Context + useReducer) | Lightweight, sufficient for game state |
| Backend API | **Node.js + Fastify + TypeScript** | TypeScript consistency, excellent Anthropic SDK |
| Job queue | **BullMQ + Redis** | Industry-standard async processing with rate limiting |
| Database | **PostgreSQL** | Relational integrity, JSONB flexibility, efficient random selection |
| Frontend hosting | **Vercel** | CDN distribution, free tier, instant deploys |
| Backend hosting | **Railway** | Managed Postgres + Redis, multi-service support, ~$5–20/month |

### System architecture

The system has three main processes. The **API server** (Fastify) serves puzzles to the frontend from PostgreSQL and records game results. The **worker process** (BullMQ) runs background puzzle generation jobs against the Claude API, validates them through the embedding and LLM pipeline, and stores approved puzzles. A **pool monitor** (BullMQ repeatable job, every 5 minutes) checks puzzle pool levels and queues generation jobs when stock drops below threshold.

Maintain **50+ validated puzzles per difficulty-configuration combination**. When the pool for any category drops below 20, the monitor queues generation jobs with elevated priority. Rate-limit Claude API calls to 10 per minute via BullMQ's built-in limiter. Set job retry to 3 attempts with exponential backoff for API failures.

### Database schema for extensibility

The schema uses a `puzzle_configs` table that parameterizes `num_groups` and `words_per_group`, enabling variable puzzle sizes (3×3 mini, 4×4 classic, 5×4 extended). Core tables: `puzzles` (metadata, difficulty score, generation model, validation score, play statistics), `puzzle_groups` (category name, difficulty rank, color, sort order), `puzzle_words` (word text, display text, unique constraint per puzzle), and `game_sessions` (user results with JSONB guess history).

For serving random unplayed puzzles efficiently, use a materialized view or maintain a Redis set of available puzzle IDs per difficulty tier, randomly sampling from it. The `TABLESAMPLE` PostgreSQL feature can also work at moderate scale.

---

## Existing projects provide a strong foundation to build on

The open-source ecosystem offers validated patterns across the stack. **and-computers/react-connections-game** (55 stars, React + Tailwind + shadcn/ui) is the best frontend reference, using React Context for state management with faithful NYT-style UI. **lechmazur/nyt-connections** (188 stars) provides a dataset of **940 published NYT puzzles** — invaluable for few-shot examples and validation benchmarking. **Rperry2174/crossword-generator** demonstrates the clean separation of LLM service from puzzle logic in a React + FastAPI architecture.

The **Swellgarfo Connections Creator** — a simple manual puzzle creator used over **7 million times** before NYT sent a cease-and-desist — proves massive consumer demand for custom Connections puzzles. An AI-generated infinite puzzle feed fills this unmet need. Commercially, **Puzzel.org's PuzzleGPT** shows that LLM-integrated puzzle generation works as a product across multiple puzzle types.

The key lesson from failed approaches: **LLMs lack metacognition about human difficulty perception.** They can generate valid word groups rapidly (listing "30 shades of green in seconds") but cannot model what a human player would find tricky versus obvious. This is precisely why the embedding-based difficulty calibration and solver-agent validation are essential complements to generation.

---

## Cost optimization can reduce per-puzzle expense by 85%

### Model tiering strategy

Use **Sonnet 4.5** ($3/$15 per million tokens) for creative generation steps — best balance of quality and cost. Use **Haiku 4.5** ($1/$5 per million tokens) for all validation, difficulty scoring, and solver-agent checks. Reserve **Opus 4.5** ($5/$25) only if Sonnet quality proves insufficient for specific category types (unlikely based on current benchmarks).

### Three compounding cost reducers

**Prompt caching** delivers up to **90% savings** on input tokens. Place the system prompt, category style templates, and all few-shot examples (10–20 puzzles) in a cached prefix marked with `cache_control`. Cache reads cost just 0.1× the base input rate. With a 5-minute default TTL that refreshes on each use, steady generation keeps the cache hot.

**Batch API processing** provides a flat **50% discount** on all tokens. Submit batches of 50–100 puzzle generation requests asynchronously — most complete within 1 hour. Combine with 1-hour cache TTL (available at 2× write cost, but still net positive with batch discount) for maximum savings.

**Smart retry logic** avoids wasting money on doomed generations. Validate JSON structure (guaranteed with structured outputs), check constraint satisfaction programmatically, and run embedding checks before expensive LLM solver validation. If a puzzle fails structural checks, retry with error context appended — not the identical prompt. Cap retries at 3, then adjust prompt parameters or fall back to a more capable model.

### Per-puzzle cost estimate

A 3-call pipeline (generate + refine + validate) costs approximately **$0.03 without optimization**. With prompt caching: **$0.01–0.015**. With batch API added: **$0.005–0.008 per puzzle**. At $0.008 per puzzle, a pool of 500 validated puzzles costs just $4.00 to generate. Even accounting for a ~40% validation rejection rate, the total cost for 500 published puzzles is under $7.

---

## Extensibility requires parameterization at every layer

The system should treat the classic 4×4 configuration as one instance of a general `(num_groups, words_per_group)` parameter space. This affects four layers:

**Generation prompts** must accept `numGroups` and `wordsPerGroup` as variables, adjusting instructions accordingly ("Generate {numGroups} categories with {wordsPerGroup} words each"). Difficulty parameterization maps to prompt variables: `overlapStrategy` (none/subtle/intentional), `categoryTypes` (semantic/wordplay/cultural/linguistic), and `wordComplexity` (simple/moderate/advanced).

**Validation thresholds** scale with configuration. A 3×3 mini puzzle needs tighter within-group coherence (fewer words means each must clearly belong). A 5×5 extended puzzle can tolerate slightly lower coherence since more words provide redundant signal.

**The database schema** already supports this through the `puzzle_configs` table — any combination from 3×3 mini to 6×4 mega uses the same storage model.

**The frontend grid** renders dynamically: `gridTemplateColumns: repeat(${wordsPerGroup}, 1fr)` adapts to any column count. Selection logic validates that exactly `wordsPerGroup` tiles are selected before allowing a guess submission. The number of allowed mistakes scales with `numGroups` by default but can be overridden per config.

---

## Conclusion

The path to high-quality LLM-generated Connections puzzles is well-charted by academic research and validated by existing implementations. Three insights stand out as non-obvious. First, **diversity injection through creative seed stories** is more effective than explicit "be diverse" instructions — it exploits LLMs' narrative strengths rather than fighting their tendency toward repetition. Second, **embedding cosine similarity thresholds are remarkably predictive** of human difficulty perception, providing an objective calibration mechanism that compensates for LLMs' inability to model human cognition. Third, the **economics are surprisingly favorable**: at under $0.01 per validated puzzle with batching and caching, the constraint is not cost but quality control — building a robust enough validation pipeline that every puzzle reaching players is genuinely fun to solve. The recommended architecture — iterative multi-step generation with Sonnet, embedding-based validation with MPNet, LLM solver verification with Haiku, and a pre-generated pool served from PostgreSQL — provides the scaffolding to achieve this at scale.