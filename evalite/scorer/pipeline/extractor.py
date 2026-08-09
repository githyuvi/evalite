"""Extractor stage of PipelineScorer (ADR-007 Decision 3, ADR-008).

An `Extractor` pulls individual claim/fact strings out of an agent's raw
response so they can be classified one at a time by a `Judge`. Built-ins:

- `LLMExtractor` — default; asks an `LLMProvider` to list discrete factual
  claims from unstructured text.
- `PatternExtractor` — regex and/or a minimal, dependency-free JSONPath
  subset for structured/semi-structured responses. No LLM required.

`PatternExtractor`'s JSONPath support reimplements the same minimal subset
(dot-separated keys + `[N]` list indexing, e.g. `"$.result.items[0].name"`)
that `evalite/scorer/json_path.py`'s `JsonPathScorer` uses. That module does
not expose a standalone resolver function — its `_resolve` is a private
method bound to a `JsonPathScorer` instance's `self.path` — so the same
logic is reimplemented locally here as a module-level function rather than
reaching into another class's private method or adding a JSONPath library
dependency (ADR-008: PatternExtractor must work airgapped, zero new deps).
"""

import json
import re
from typing import Any, Protocol

from evalite.llm.provider import LLMProvider


class Extractor(Protocol):
    """Structural contract for pulling claims/facts out of a response."""

    async def extract(self, response: str, expected: dict) -> list[str]:
        """Return a list of individual claim/fact strings extracted from response."""
        ...


def _resolve_json_path(data: Any, path: str) -> tuple[bool, Any]:
    """Resolve a minimal JSONPath-subset expression against `data`.

    Supports dot-separated keys and `[N]` list indexing, e.g.
    `"$.result.items[0].name"`. Mirrors the logic in
    `evalite.scorer.json_path.JsonPathScorer._resolve`.

    Returns:
        (resolved, value) — resolved is False if the path could not be
        resolved (missing key, out-of-range index, non-dict/list traversal,
        malformed segment), matching JsonPathScorer's tolerant behavior.
    """
    segments = path.split(".")
    if not segments or segments[0] != "$":
        return False, None

    current = data
    for segment in segments[1:]:
        key = segment
        index: int | None = None

        if segment.endswith("]") and "[" in segment:
            bracket_pos = segment.index("[")
            key = segment[:bracket_pos]
            index_str = segment[bracket_pos + 1 : -1]
            if not index_str.lstrip("-").isdigit():
                return False, None
            index = int(index_str)

        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]

        if index is not None:
            if not isinstance(current, list):
                return False, None
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]

    return True, current


_EXTRACTION_SYSTEM_PROMPT = (
    "You extract discrete factual claims from an agent's response so each "
    "can be evaluated independently. Read the response below and list every "
    "individual factual claim it makes as a JSON array of strings, e.g. "
    '["claim one", "claim two"]. Each array element must be a single, '
    "self-contained claim. Respond with ONLY the JSON array — no other text."
)


class LLMExtractor:
    """Extracts discrete factual claims from unstructured text via an LLM.

    Builds a prompt asking the provider to list each factual claim in
    `response` as a JSON array of strings, calls `provider.complete`, and
    parses the result into `list[str]`.

    Degradation: if the completion cannot be parsed as a JSON array of
    strings, the raw completion text is returned as a single-item list
    (`[completion]`) instead of raising — extraction should degrade
    gracefully rather than crash a run over LLM output formatting.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def extract(self, response: str, expected: dict) -> list[str]:
        if not response.strip():
            return []

        user_prompt = (
            "Expected outcomes/context (JSON):\n"
            f"{json.dumps(expected, default=str)}\n\n"
            "Response to extract claims from:\n"
            f"{response}"
        )
        messages = [
            {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        completion = await self.provider.complete(messages)

        try:
            parsed = json.loads(completion)
            if not isinstance(parsed, list) or not all(
                isinstance(item, str) for item in parsed
            ):
                raise ValueError("expected a JSON array of strings")
        except (json.JSONDecodeError, ValueError):
            return [completion]

        return parsed


class PatternExtractor:
    """Extracts items from structured/semi-structured responses.

    No LLM dependency; works airgapped (ADR-008).

    - `patterns`: a list of regex strings applied to `response` via
      `re.findall`. For a pattern with no capturing groups, each full match
      becomes one extracted item. For a pattern with capturing groups,
      `re.findall` returns tuples of group values; each non-empty group
      value becomes its own extracted item (flattened).
    - `json_path`: a JSONPath-subset expression (see `_resolve_json_path`)
      resolved against `response` parsed as JSON. If the resolved value is
      a list, each element is stringified into its own item; otherwise the
      single resolved value is stringified into a one-item contribution.
      If `response` is not valid JSON, or the path does not resolve, the
      json_path contribution is an empty list (degrades gracefully,
      consistent with `JsonPathScorer`'s tolerance of malformed input).

    If both `patterns` and `json_path` are given, results from `patterns`
    are computed first, then `json_path`, and the two lists are
    concatenated.
    """

    def __init__(
        self,
        patterns: list[str] | None = None,
        json_path: str | None = None,
    ) -> None:
        self.patterns = patterns
        self.json_path = json_path

    def _extract_patterns(self, response: str) -> list[str]:
        items: list[str] = []
        for pattern in self.patterns or []:
            for match in re.findall(pattern, response):
                if isinstance(match, tuple):
                    items.extend(group for group in match if group)
                else:
                    items.append(match)
        return items

    def _extract_json_path(self, response: str) -> list[str]:
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return []

        resolved, value = _resolve_json_path(data, self.json_path)
        if not resolved:
            return []

        if isinstance(value, list):
            return [str(element) for element in value]
        return [str(value)]

    async def extract(self, response: str, expected: dict) -> list[str]:
        items: list[str] = []
        if self.patterns:
            items.extend(self._extract_patterns(response))
        if self.json_path:
            items.extend(self._extract_json_path(response))
        return items
