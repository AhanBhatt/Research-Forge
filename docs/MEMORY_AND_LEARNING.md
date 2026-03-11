# Memory And Learning

This document explains how Research Forge stores long-term memory, how it uses that memory in later runs, and how the self-improvement loop is implemented.

## Memory Layers

Research Forge uses two persistence layers:

1. Neo4j graph memory
2. Local JSON strategy cache

Neo4j stores structured research objects and relationships. The local strategy cache stores reflection-derived strategy updates even when Neo4j is disabled.

## Neo4j Data Model

Neo4j writes are handled in [`tools/neo4j_store.py`](/d:/Projects/Research%20Forge/tools/neo4j_store.py).

### Main node types

- `Topic`
- `Paper`
- `Author`
- `Concept`
- `Method`
- `Dataset`
- `Metric`
- `Assumption`
- `Limitation`
- `Claim`
- `Hypothesis`
- `Experiment`
- `Result`
- `FailureMode`
- `ResearchIdea`
- `StrategyUpdate`

### Main relationships

- `Paper -[:ABOUT_TOPIC]-> Topic`
- `Paper -[:AUTHORED_BY]-> Author`
- `Paper -[:DISCUSSES]-> Concept`
- `Paper -[:USES_METHOD]-> Method`
- `Paper -[:EVALUATED_ON]-> Dataset`
- `Paper -[:MEASURES_WITH]-> Metric`
- `Paper -[:ASSUMES]-> Assumption`
- `Paper -[:HAS_LIMITATION]-> Limitation`
- `Paper -[:CLAIMS]-> Claim`
- `Hypothesis -[:ABOUT_TOPIC]-> Topic`
- `Hypothesis -[:INSPIRED_BY]-> Paper`
- `Experiment -[:TESTS]-> Hypothesis`
- `Experiment -[:PRODUCED]-> Result`
- `Result -[:REVEALS]-> FailureMode`
- `ResearchIdea -[:ABOUT_TOPIC]-> Topic`
- `ResearchIdea -[:DERIVED_FROM]-> Result`
- `StrategyUpdate -[:ABOUT_TOPIC]-> Topic`
- `StrategyUpdate -[:BASED_ON]-> Result`

## What Gets Written And When

### During `update_graph_memory`

The system writes:

- topic node
- paper nodes
- author nodes
- category concepts
- extraction-linked method, dataset, metric, assumption, limitation, and claim nodes

### During `prioritize_hypotheses`

The system writes:

- hypothesis nodes
- `INSPIRED_BY` edges to grounding papers

### During `plan_experiment`

The system writes:

- experiment nodes
- `TESTS` edges to hypotheses

### During `run_experiment`

The system writes:

- result nodes
- `PRODUCED` edges from experiments
- failure modes revealed by confounders

### During `update_strategy`

The system writes:

- strategy update nodes
- `BASED_ON` edges to results where available

### During `generate_final_report`

The system writes:

- research idea nodes
- `DERIVED_FROM` edges to executed results

## How Memory Is Read

Memory reads are intentionally narrow and schema-aware.

The retrieval logic is in [`memory/retrieval.py`](/d:/Projects/Research%20Forge/memory/retrieval.py).

### Related concepts

At topic ingestion time, the agent asks:

- what concepts already co-occur with papers about this topic?

This helps later heuristic hypothesis generation.

### Previous hypothesis outcomes

During heuristic hypothesis generation, the agent asks:

- which prior hypotheses on this topic were supported, unsupported, or unknown?

This lets it derive new hypotheses from past failures instead of starting from scratch every time.

## Strategy Memory

The strategy layer lives in [`memory/strategy_memory.py`](/d:/Projects/Research%20Forge/memory/strategy_memory.py).

It does two things:

- loads previous strategy hints at the start of a run
- persists new strategy updates at the end of a run

Strategy hints can come from:

- Neo4j `StrategyUpdate` nodes
- local JSON cache at `LOCAL_STRATEGY_CACHE_PATH`

Hints are deduplicated and passed into hypothesis generation prompts.

## Reflection And Self-Improvement

The self-improvement loop is implemented in [`agent/nodes/reflect.py`](/d:/Projects/Research%20Forge/agent/nodes/reflect.py).

It explicitly tracks:

- what the system predicted
- what happened
- whether those aligned
- how good the query strategy was
- how confident extraction was
- whether experiments actually ran

### Strategy update categories

- `query`
  Whether the retrieval style produced enough useful evidence.
- `extraction`
  Whether the prompt yielded sufficiently confident structured objects.
- `hypothesis`
  Whether priority-based predictions matched actual outcomes.
- `experiment`
  Whether planned experiments were actually executable.
- `evaluation`
  Reserved by schema even if not always emitted yet.

### Strategy update fields

Each `StrategyUpdate` includes:

- `predicted`
- `observed`
- `failure_or_success_reason`
- `recommendation`
- `confidence_delta`
- `impact_score`
- optional result links

This is what makes the self-improvement concrete instead of purely narrative.

## Local Strategy Cache

The local cache exists so the system still accumulates learning without Neo4j.

Behavior:

- stored as JSON
- keyed by topic
- newest updates appended
- last 100 retained per topic

This lets later runs benefit from prior recommendations even in a lightweight local setup.

## Key Graph View In The UI

The Streamlit graph view is built from the run artifact, not directly from Neo4j.

Current semantics:

- `Paper -> Topic` with `ABOUT_TOPIC`
- `Hypothesis -> Topic` with `ABOUT_TOPIC`
- `Hypothesis -> Paper` with `INSPIRED_BY`
- `Experiment -> Hypothesis` with `TESTS`
- `Experiment -> Result` with `PRODUCED`
- `Result -> FailureMode` with `REVEALS`

The graph view is useful as a causal run summary. It is not yet a general-purpose graph explorer for arbitrary Neo4j neighborhoods.

## Failure And Graceful Degradation

Neo4j is optional by design.

If initialization fails or the configured database does not exist:

- writes are disabled
- warnings are logged
- the agent still runs
- local strategy caching still works

This keeps memory as an enhancement rather than a hard dependency.
