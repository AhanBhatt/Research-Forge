# Sample Run Output (Illustrative, Current)

Run ID: `run_3f8d1a91b6c2`  
Topic: `LLM evaluation`

## Summary
- Papers ranked: 12
- Hypotheses generated: 7
- Experiments attempted: 2
- Experiments executed: 1

## Example Hypothesis
`hyp_a12ff40c`  
Applying constrained decoding during extraction will increase relation consistency by at least 3% on low-resource evaluation tasks compared to unconstrained decoding.

## Example Experiment Result
`exp_84ff3d7a`  
Status: executed  
Outcome: supported  
Metric deltas:
- `primary_score`: `+0.0351`
- `runtime_cost`: `+0.0500`

## Strategy Update Example
- Category: `hypothesis`
- Predicted: `hyp_a12ff40c support_probability=0.68`
- Observed: `outcome=supported`
- Recommendation: `Increase confidence in this hypothesis scoring pattern.`

## Notes
- Neo4j warnings can appear on empty/new graphs and are usually non-fatal.
- If Neo4j is optional for your workflow, disable `NEO4J_*` values in `.env`.
