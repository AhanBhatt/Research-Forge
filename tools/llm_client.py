"""OpenAI-compatible LLM wrapper with structured output helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from config import Settings

LOGGER = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Client that hides provider-specific details and parse retries."""

    def __init__(self, settings: Settings) -> None:
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.enabled = settings.llm_enabled
        self._client = None
        if self.enabled:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
            except Exception as exc:  # pragma: no cover - import/runtime edge cases
                LOGGER.warning("LLM client initialization failed, switching to offline mode: %s", exc)
                self.enabled = False

    def chat(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        """Run a chat completion request and return assistant text."""

        if not self.enabled or self._client is None:
            raise RuntimeError("LLM is not configured.")

        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        completion = self._client.chat.completions.create(**payload)
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise RuntimeError("LLM returned empty content.")
        return content

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        retries: int = 2,
        fallback_factory: Callable[[], T] | None = None,
    ) -> T:
        """Generate and validate a typed response from the LLM."""

        if not self.enabled:
            if fallback_factory:
                return fallback_factory()
            raise RuntimeError("LLM disabled and no fallback provided.")

        attempts = max(1, retries + 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                text = self.chat(system_prompt=system_prompt, user_prompt=user_prompt, json_mode=True)
                data = self._parse_json_payload(text)
                data = self._normalize_for_schema(data, schema)
                return schema.model_validate(data)
            except (RuntimeError, ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                LOGGER.warning("Structured LLM parse failed: %s", exc)

        if fallback_factory:
            LOGGER.info("Using fallback factory after structured parse retries.")
            return fallback_factory()
        raise RuntimeError(f"Structured generation failed: {last_error}") from last_error

    @staticmethod
    def _parse_json_payload(text: str) -> dict[str, object]:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Recover from models returning fenced JSON blocks.
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    @staticmethod
    def _normalize_for_schema(data: dict[str, object], schema: type[T]) -> dict[str, object]:
        """Coerce common model-output variants into expected schema shape."""

        name = schema.__name__

        if name == "ResearchObjectExtraction":
            alias_map = {
                "problem": "research_problem",
                "research_question": "research_problem",
                "method": "method_summary",
                "approach": "method_summary",
            }
            for src, dst in alias_map.items():
                if dst not in data and src in data:
                    data[dst] = data[src]

            for list_key in [
                "datasets",
                "metrics",
                "assumptions",
                "limitations",
                "future_work",
                "reproducibility_clues",
                "follow_up_hypotheses",
                "main_claims",
            ]:
                value = data.get(list_key)
                if isinstance(value, dict):
                    data[list_key] = [str(v) for v in value.values() if isinstance(v, (str, int, float))]
                elif isinstance(value, list):
                    normalized: list[str] = []
                    for item in value:
                        if isinstance(item, str):
                            normalized.append(item)
                        elif isinstance(item, dict):
                            for key in ("name", "title", "description", "claim", "text"):
                                if isinstance(item.get(key), str):
                                    normalized.append(item[key])
                                    break
                            else:
                                normalized.append(json.dumps(item))
                        else:
                            normalized.append(str(item))
                    data[list_key] = normalized

        if name == "HypothesisBatch" and isinstance(data.get("hypotheses"), list):
            normalized_hypotheses: list[dict[str, object]] = []
            for idx, item in enumerate(data["hypotheses"]):  # type: ignore[index]
                if not isinstance(item, dict):
                    continue
                statement = item.get("statement") or item.get("hypothesis") or item.get("idea")
                rationale = item.get("rationale") or "Generated from extracted evidence and identified gaps."
                grounding = item.get("grounding_papers", [])
                if isinstance(grounding, str):
                    grounding = [grounding]
                elif not isinstance(grounding, list):
                    grounding = []
                normalized_hypotheses.append(
                    {
                        "hypothesis_id": item.get("hypothesis_id") or f"hyp_auto_{idx}",
                        "statement": statement or "No statement provided.",
                        "rationale": rationale,
                        "grounding_papers": grounding,
                        "novelty": LLMClient._normalize_unit_interval(item.get("novelty", 0.5)),
                        "feasibility": LLMClient._normalize_unit_interval(item.get("feasibility", 0.5)),
                        "information_gain": LLMClient._normalize_unit_interval(
                            item.get("information_gain", item.get("expected_information_gain", 0.5))
                        ),
                        "compute_cost": LLMClient._normalize_unit_interval(item.get("compute_cost", 0.5)),
                        "expected_direction": item.get("expected_direction", "unknown"),
                        "priority_score": LLMClient._normalize_unit_interval(item.get("priority_score", 0.5)),
                    }
                )
            data["hypotheses"] = normalized_hypotheses

        return data

    @staticmethod
    def _normalize_unit_interval(value: object) -> float:
        """Normalize model score formats to [0, 1]."""

        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.5

        if score > 1.0:
            # Common model behavior: output rubric scores on a 1-10 scale.
            if score <= 10.0:
                score = score / 10.0
            else:
                score = 1.0
        if score < 0.0:
            score = 0.0
        return round(score, 4)
