"""Reusable Cypher snippets for memory retrieval."""

STRATEGY_HINTS_QUERY = """
MATCH (s:StrategyUpdate)-[:ABOUT_TOPIC]->(t:Topic {name: $topic})
RETURN s.recommendation AS recommendation
ORDER BY s.timestamp DESC
LIMIT $limit
"""

RELATED_CONCEPTS_QUERY = """
MATCH (p:Paper)-[:ABOUT_TOPIC]->(t:Topic {name: $topic})
MATCH (p)-[:DISCUSSES]->(c:Concept)
RETURN c.name AS concept, count(*) AS frequency
ORDER BY frequency DESC
LIMIT $limit
"""

HYPOTHESIS_OUTCOMES_QUERY = """
MATCH (h:Hypothesis)-[:ABOUT_TOPIC]->(t:Topic {name: $topic})
OPTIONAL MATCH (e:Experiment)-[:TESTS]->(h)-[:ABOUT_TOPIC]->(t)
OPTIONAL MATCH (e)-[:PRODUCED]->(r:Result)
RETURN h.hypothesis_id AS hypothesis_id, h.statement AS statement, r.hypothesis_outcome AS outcome
LIMIT $limit
"""
