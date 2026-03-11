# Getting Started

This guide covers local setup, configuration, CLI usage, UI usage, Neo4j setup, and testing.

## Prerequisites

- Python 3.11+ recommended
- A valid OpenAI-compatible API key
- Optional: Neo4j local instance or Neo4j Aura

## Installation

1. Open a terminal in the project root:
   ```powershell
   cd "D:\Projects\Research Forge"
   ```
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Create `.env` from `.env.example`:
   ```powershell
   Copy-Item .env.example .env
   ```

## Environment Variables

The project reads configuration through [`config.py`](/d:/Projects/Research%20Forge/config.py).

### LLM settings

- `OPENAI_API_KEY`
  Required unless you want all LLM-backed behavior to fall back or fail.
- `OPENAI_BASE_URL`
  Default: `https://api.openai.com/v1`
- `OPENAI_MODEL`
  Default: `gpt-4.1-mini`
- `OPENAI_TEMPERATURE`
  Default: `0.2`

### arXiv settings

- `ARXIV_API_URL`
  Default: `https://export.arxiv.org/api/query`
- `ARXIV_TIMEOUT_SECONDS`
  Default: `20`
- `ARXIV_MAX_RETRIES`
  Default: `2`
- `ARXIV_BACKOFF_SECONDS`
  Default: `2.0`
- `ARXIV_MAX_RESULTS_PER_QUERY`
  Default: `16`

### Neo4j settings

- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`

If any required Neo4j credential is missing, graph writes are disabled and the rest of the system continues.

### Experiment and artifact settings

- `EXPERIMENT_TIMEOUT_SECONDS`
  Timeout for sandboxed experiment snippets.
- `MAX_EXTRACTION_RETRIES`
  Structured extraction retry count for LLM parsing.
- `ARTIFACTS_DIR`
  Default artifact directory.
- `LOCAL_STRATEGY_CACHE_PATH`
  JSON file used for local strategy memory fallback.

## Basic CLI Usage

The CLI entry point is [`app.py`](/d:/Projects/Research%20Forge/app.py).

### Example run

```powershell
.\.venv\Scripts\python.exe app.py --topic "LLM evaluation" --max-papers 12 --categories "cs.CL,cs.LG" --experiment-budget 2
```

### CLI flags

- `--topic`
  Required research topic string.
- `--max-papers`
  Number of ranked papers to keep after retrieval.
- `--categories`
  Comma-separated arXiv categories, for example `cs.CL,cs.LG`.
- `--date-from`
  Lower date bound in `YYYY-MM-DD`.
- `--date-to`
  Upper date bound in `YYYY-MM-DD`.
- `--experiment-budget`
  Maximum number of top hypotheses to plan directly for experimentation.
- `--no-experiments`
  Disables all local experiment execution and forces theoretical-only experiment handling.

### Typical CLI output

The CLI prints:

- Run ID
- Topic
- Summary counters
- Markdown artifact path
- JSON artifact path

## Streamlit Usage

The UI lives in [`ui/streamlit_app.py`](/d:/Projects/Research%20Forge/ui/streamlit_app.py).

### Start the UI

```powershell
.\.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py
```

### What the UI lets you do

- Enter a research topic
- Set max papers
- Set experiment budget
- Toggle experiments on or off
- Set preferred arXiv categories
- Set a date range
- Launch the agent
- Inspect retrieved papers, hypotheses, experiment plans, results, strategy updates, and graph view

## Neo4j Setup

### Option A: Run without Neo4j

Leave the Neo4j variables empty in `.env`:

```env
NEO4J_URI=
NEO4J_USER=
NEO4J_PASSWORD=
NEO4J_DATABASE=
```

### Option B: Run with Neo4j

Populate valid credentials:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
```

### Verify runtime config

```powershell
.\.venv\Scripts\python.exe -c "from config import get_settings; s=get_settings(); print(s.neo4j_uri, s.neo4j_database, s.neo4j_enabled)"
```

## Artifacts

Each run creates:

- `artifacts/<run_id>/research_report.md`
- `artifacts/<run_id>/research_report.json`

The JSON artifact is the machine-readable canonical record. The Markdown file is a human-readable summary.

## Running Tests

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Useful targeted test runs:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_arxiv_client.py tests/test_plan_experiment.py tests/test_llm_client.py -q
```

## Example Starter Topics

See [examples/example_topics.md](/d:/Projects/Research%20Forge/examples/example_topics.md).

Good first topics:

- `LLM evaluation`
- `anomaly detection`
- `time series forecasting under concept drift`

Topics like `protein folding` or other heavy scientific domains are supported conceptually, but local experiment execution will usually remain theoretical-only.
