# Troubleshooting

This guide covers the most common runtime issues seen in local runs.

## 1. Streamlit import error: `ModuleNotFoundError: No module named 'agent'`

### Symptom

- Running `streamlit run ui/streamlit_app.py` crashes with import error.

### Fix

1. Run from project root:
   ```powershell
   cd "D:\Projects\Research Forge"
   ```
2. Start Streamlit via project venv:
   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py
   ```
3. If previously running, stop (`Ctrl+C`) and restart.

## 2. Neo4j warning: `DatabaseNotFound` / routing table errors

### Symptom

- Warnings like:
  - `Unable to get a routing table for database ...`
  - `DatabaseNotFound`
  - repeated graph write warnings

### Fix Option A: Disable Neo4j (quickest)

Set Neo4j values empty in `.env`:

```env
NEO4J_URI=
NEO4J_USER=
NEO4J_PASSWORD=
NEO4J_DATABASE=
```

### Fix Option B: Use Neo4j correctly

1. Set valid values in `.env`.
2. Confirm runtime config:
   ```powershell
   .\.venv\Scripts\python.exe -c "from config import get_settings; s=get_settings(); print(s.neo4j_uri, s.neo4j_database, s.neo4j_enabled)"
   ```
3. Ensure the target database actually exists in your Neo4j deployment.

## 3. arXiv query failures

### Symptom

- Warnings with `arXiv query failed` and no papers retrieved.
- Errors like `429 Too Many Requests` or `Read timed out`.

### Fix

1. Ensure `.env` has:
   ```env
   ARXIV_API_URL=https://export.arxiv.org/api/query
   ARXIV_MAX_RETRIES=2
   ARXIV_BACKOFF_SECONDS=2.0
   ARXIV_MAX_RESULTS_PER_QUERY=16
   ```
2. Test connectivity:
   ```powershell
   .\.venv\Scripts\python.exe -c "import requests; print(requests.get('https://export.arxiv.org/api/query?search_query=all:llm&max_results=1',timeout=20).status_code)"
   ```
3. If you still hit `429`, lower request pressure:
   - set `ARXIV_MAX_RESULTS_PER_QUERY=10`
   - set `ARXIV_BACKOFF_SECONDS=4.0`
   - temporarily reduce CLI `--max-papers` (for example `8`)
4. If blocked entirely, check local firewall/proxy/network policy.

## 4. LLM structured parse warnings

### Symptom

- Warnings about structured schema mismatch.

### Status

- The agent has fallback parsing/normalization and usually continues.
- These warnings are non-fatal unless a hard exception follows.

### Fix

1. Keep using current codebase (normalizers were added).
2. Ensure `OPENAI_MODEL` remains an instruction-following model (default works).
3. If needed, lower `MAX_EXTRACTION_RETRIES` to reduce repeated warnings/noise.

## 5. Run completes but outputs look sparse

### Symptom

- Few/no papers or hypotheses.

### Fix

1. Broaden query:
   - Remove category filter or reduce strictness.
2. Increase paper count:
   - `--max-papers 20`
3. Verify arXiv connectivity and OpenAI key are valid.

## 6. Sanity command

Run this full smoke command:

```powershell
.\.venv\Scripts\python.exe app.py --topic "LLM evaluation" --max-papers 12 --categories "cs.CL,cs.LG" --experiment-budget 2
```

Expected end-state:

- `Run complete: run_<id>`
- Artifacts written under `artifacts/<run_id>/`
