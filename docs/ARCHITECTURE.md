# Architecture

This document explains how Research Forge is assembled, how state flows through the system, and what each module is responsible for.

## Top-Level Structure

The main runtime pieces are:

- [`app.py`](/d:/Projects/Research%20Forge/app.py)
  CLI entry point.
- [`agent/graph.py`](/d:/Projects/Research%20Forge/agent/graph.py)
  LangGraph assembly, dependency wiring, and fallback final report generation.
- [`agent/state.py`](/d:/Projects/Research%20Forge/agent/state.py)
  Shared mutable run state.
- [`agent/nodes/`](/d:/Projects/Research%20Forge/agent/nodes)
  Workflow node implementations.
- [`tools/`](/d:/Projects/Research%20Forge/tools)
  External systems and utility adapters.
- [`memory/`](/d:/Projects/Research%20Forge/memory)
  Cross-run memory retrieval and persistence helpers.
- [`schemas/`](/d:/Projects/Research%20Forge/schemas)
  Pydantic contracts for requests, papers, extractions, hypotheses, plans, results, and reports.
- [`ui/streamlit_app.py`](/d:/Projects/Research%20Forge/ui/streamlit_app.py)
  Demo UI.

## Execution Model

The system uses a sequential LangGraph state machine. Each node:

- reads the current validated state
- produces a partial state update
- appends logs and sometimes errors
- optionally writes to Neo4j or local artifacts

All node functions are wrapped by a defensive adapter in [`agent/graph.py`](/d:/Projects/Research%20Forge/agent/graph.py). If a node raises an exception, the graph does not crash immediately. Instead, the wrapper records the error in state and continues. If the workflow finishes without a `final_report`, the agent builds a fallback report from whatever state was successfully accumulated.

## Shared State

The canonical run state lives in [`agent/state.py`](/d:/Projects/Research%20Forge/agent/state.py).

Important state channels:

- `request`
  The topic and user constraints.
- `query_text`
  The main arXiv query string for this run.
- `query_attempts`
  Query variants attempted by the arXiv client.
- `papers`
  Raw retrieved paper candidates.
- `ranked_papers`
  Top papers after scoring.
- `extractions`
  Structured research objects keyed by arXiv ID.
- `hypotheses`
  Generated hypotheses.
- `prioritized_hypotheses`
  Hypotheses selected for planning.
- `predictions`
  Expected support probabilities used for reflection.
- `experiment_plans`
  Planned experiments.
- `experiment_results`
  Executed or skipped experiment results.
- `strategy_snapshot`
  Prior strategy hints loaded at the beginning of the run.
- `strategy_updates`
  New learning signals produced during reflection.
- `reflection_notes`
  Human-readable notes about what happened.
- `final_report`
  Final `RunReport` object.

## Node-by-Node Workflow

### `ingest_topic`

File: [`agent/nodes/ingest_topic.py`](/d:/Projects/Research%20Forge/agent/nodes/ingest_topic.py)

Responsibilities:

- normalizes the topic string
- loads prior strategy hints from strategy memory
- retrieves related concepts from Neo4j memory
- initializes `query_text`

Current behavior:

- the arXiv query text stays focused on the user topic
- category filters are handled later in the arXiv client instead of being merged into the topic string

### `query_papers`

File: [`agent/nodes/query_papers.py`](/d:/Projects/Research%20Forge/agent/nodes/query_papers.py)

Responsibilities:

- calls the arXiv client
- passes topic, max results, category filters, and date filters
- records query attempts and retrieval count

The arXiv client:

- prefers HTTPS
- handles retries and backoff
- uses a capped result size per query
- broadens queries if the initial query is too narrow
- cools down on `429 Too Many Requests`

### `rank_papers`

File: [`agent/nodes/rank_papers.py`](/d:/Projects/Research%20Forge/agent/nodes/rank_papers.py)

Responsibilities:

- computes ranking scores using the ranker
- retains only the requested number of top papers

### `extract_research_objects`

File: [`agent/nodes/extract_research_objects.py`](/d:/Projects/Research%20Forge/agent/nodes/extract_research_objects.py)

Responsibilities:

- runs LLM extraction with schema validation
- falls back to heuristic extraction on failure
- records average extraction confidence

The extraction schema includes:

- research problem
- main claims
- method summary
- assumptions
- datasets
- metrics
- limitations
- future work
- reproducibility clues
- follow-up hypotheses
- confidence score

### `update_graph_memory`

File: [`agent/nodes/update_graph_memory.py`](/d:/Projects/Research%20Forge/agent/nodes/update_graph_memory.py)

Responsibilities:

- writes the topic
- writes ranked papers
- writes extraction-linked entities into Neo4j

If Neo4j is disabled or unavailable, this step is skipped cleanly.

### `generate_hypotheses`

File: [`agent/nodes/generate_hypotheses.py`](/d:/Projects/Research%20Forge/agent/nodes/generate_hypotheses.py)

Responsibilities:

- calls the LLM for structured hypothesis generation
- includes prior strategy hints in the prompt
- falls back to heuristic hypothesis generation
- deduplicates hypotheses by normalized statement text

The heuristic generator uses:

- paper limitations
- extracted metrics
- method transfer between top papers
- prior unsupported outcomes from memory

### `prioritize_hypotheses`

File: [`agent/nodes/prioritize_hypotheses.py`](/d:/Projects/Research%20Forge/agent/nodes/prioritize_hypotheses.py)

Responsibilities:

- computes `priority_score`
- sorts hypotheses
- keeps the top set for planning
- creates prediction records used later in reflection
- writes hypotheses to Neo4j

### `plan_experiment`

File: [`agent/nodes/plan_experiment.py`](/d:/Projects/Research%20Forge/agent/nodes/plan_experiment.py)

Responsibilities:

- creates experiment plans from top hypotheses
- uses the LLM when possible
- falls back to heuristic planning
- upgrades non-executable lightweight plans into runnable proxy experiments

Important behavior:

- if experiments are disabled, all plans are marked theoretical-only
- lightweight topics can get auto-generated runnable snippets
- heavy topics remain theoretical-only unless a valid runnable plan already exists

### `run_experiment`

File: [`agent/nodes/run_experiment.py`](/d:/Projects/Research%20Forge/agent/nodes/run_experiment.py)

Responsibilities:

- skips execution when experiments are disabled
- skips theoretical-only or non-executable plans
- runs safe snippets through the sandbox runner
- parses `RESULT_JSON`
- writes results to Neo4j

### `evaluate_results`

File: [`agent/nodes/evaluate_results.py`](/d:/Projects/Research%20Forge/agent/nodes/evaluate_results.py)

Responsibilities:

- evaluates metric deltas
- assigns `supported`, `unsupported`, or `inconclusive`
- updates evidence quality
- generates next-step guidance

### `reflect`

File: [`agent/nodes/reflect.py`](/d:/Projects/Research%20Forge/agent/nodes/reflect.py)

Responsibilities:

- compares predictions to outcomes
- checks whether query style produced enough evidence
- checks extraction confidence
- records experiment-execution failures or skips
- generates explicit `StrategyUpdate` objects

### `update_strategy`

File: [`agent/nodes/update_strategy.py`](/d:/Projects/Research%20Forge/agent/nodes/update_strategy.py)

Responsibilities:

- persists strategy updates into Neo4j
- persists them into a local JSON strategy cache

### `generate_final_report`

File: [`agent/nodes/generate_final_report.py`](/d:/Projects/Research%20Forge/agent/nodes/generate_final_report.py)

Responsibilities:

- assembles the final `RunReport`
- writes Markdown and JSON artifacts
- derives next research ideas
- writes those ideas to Neo4j when enabled

## Tools Layer

### arXiv client

File: [`tools/arxiv_client.py`](/d:/Projects/Research%20Forge/tools/arxiv_client.py)

Responsible for:

- query construction
- retries and rate-limit handling
- fallback query styles
- parsing Atom responses into `Paper` objects

### LLM client

File: [`tools/llm_client.py`](/d:/Projects/Research%20Forge/tools/llm_client.py)

Responsible for:

- OpenAI-compatible chat calls
- JSON-only structured output calls
- schema validation
- normalization of variant model outputs into expected schema shapes
- retries and fallback factory support

### Ranker

File: [`tools/ranker.py`](/d:/Projects/Research%20Forge/tools/ranker.py)

Responsible for paper relevance and recency scoring.

### Neo4j store

File: [`tools/neo4j_store.py`](/d:/Projects/Research%20Forge/tools/neo4j_store.py)

Responsible for:

- connection management
- optional graph writes
- schema-aware reads
- graceful disablement on configuration or database errors

### Python runner

File: [`tools/python_runner.py`](/d:/Projects/Research%20Forge/tools/python_runner.py)

Responsible for:

- AST safety checks
- banned imports and calls
- isolated subprocess execution
- timeout handling

### Report writer

File: [`tools/report_writer.py`](/d:/Projects/Research%20Forge/tools/report_writer.py)

Responsible for writing the Markdown and JSON run artifacts.

## Prompt Design

Prompt templates live in [`agent/prompts.py`](/d:/Projects/Research%20Forge/agent/prompts.py).

There are separate prompts for:

- extraction
- hypothesis generation
- experiment planning
- result evaluation support text

The design goal is to keep prompts reusable and separate from orchestration logic.

## Failure Handling Philosophy

Research Forge is intentionally designed to degrade rather than crash:

- if Neo4j is unavailable, the rest of the run still completes
- if LLM parsing fails, heuristic fallback is used where implemented
- if arXiv queries fail, errors are recorded and the run still produces an artifact
- if the final graph node fails, a fallback report is assembled from partial state
