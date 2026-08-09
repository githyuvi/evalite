"""Judge stage of PipelineScorer (ADR-007 Decision 3, ADR-008).

A `Judge` classifies each extracted item into exactly one of the supplied
`Category` objects. Built-ins:

- `LLMJudge` — default; classifies items via an `LLMProvider`.
- `RuleJudge` — deterministic keyword matching against `expected`. Zero LLM
  dependency, works airgapped (ADR-008).
"""

import json
from typing import Protocol

from evalite.llm.provider import LLMProvider

from .category import Category


class Judge(Protocol):
    """Structural contract for classifying extracted items into categories."""

    async def classify(
        self,
        items: list[str],
        categories: list[Category],
        expected: dict,
    ) -> dict[str, str]:
        """Returns {item: category_name} for each extracted item."""
        ...


def _build_base_prompt(categories: list[Category]) -> str:
    lines = [
        "You are an evaluation judge. Classify each item listed below into "
        "exactly one of the following categories:",
        "",
    ]
    for category in categories:
        lines.append(f"- {category.name}: {category.description}")
    lines.extend(
        [
            "",
            "Respond with ONLY a JSON object mapping each item's exact text "
            'to the name of the category it belongs to, e.g. {"item text": '
            '"category_name"}. Every item must be classified into exactly '
            "one category. Do not include any text outside the JSON object.",
        ]
    )
    return "\n".join(lines)


class LLMJudge:
    """Classifies extracted items into categories using an `LLMProvider`.

    The system prompt has three modes (ADR-007 Decision 3):
      - default: a base prompt (see `_build_base_prompt`) listing each
        category's name + description and asking for a JSON object mapping
        item text -> category name.
      - append: `additional_instructions` is appended below the base prompt.
      - override: `system_prompt` replaces the base prompt entirely.

    Degradation: if the provider's completion cannot be parsed as a JSON
    object, every item is classified into `categories[0]` (the first
    supplied category) rather than raising. The same per-item fallback
    applies if the parsed JSON object is missing an item, or assigns it a
    category name that is not among `categories` — a formatting slip in LLM
    output should not crash a run.
    """

    def __init__(
        self,
        provider: LLMProvider,
        additional_instructions: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.provider = provider
        self.additional_instructions = additional_instructions
        self.system_prompt = system_prompt

    def _build_system_prompt(self, categories: list[Category]) -> str:
        if self.system_prompt is not None:
            return self.system_prompt
        base = _build_base_prompt(categories)
        if self.additional_instructions:
            return f"{base}\n\n{self.additional_instructions}"
        return base

    async def classify(
        self,
        items: list[str],
        categories: list[Category],
        expected: dict,
    ) -> dict[str, str]:
        if not items:
            return {}

        fallback_category = categories[0].name

        system_prompt = self._build_system_prompt(categories)
        items_block = "\n".join(f"- {item}" for item in items)
        user_prompt = (
            "Expected outcomes/context (JSON):\n"
            f"{json.dumps(expected, default=str)}\n\n"
            "Items to classify:\n"
            f"{items_block}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = await self.provider.complete(messages)

        try:
            parsed = json.loads(completion)
            if not isinstance(parsed, dict):
                raise ValueError("expected a JSON object")
        except (json.JSONDecodeError, ValueError):
            return {item: fallback_category for item in items}

        valid_names = {category.name for category in categories}
        result: dict[str, str] = {}
        for item in items:
            category_name = parsed.get(item)
            if isinstance(category_name, str) and category_name in valid_names:
                result[item] = category_name
            else:
                result[item] = fallback_category
        return result


class RuleJudge:
    """Deterministic keyword classification. No LLM required (ADR-008).

    Rule (documented precisely, per the conservative-interpretation
    guideline — there is no LLM to interpret free-form category semantics):

    `expected`'s values are recursively flattened to strings (nested
    dicts/lists included, same flattening `DefaultScorer` uses). An item is
    classified as the category literally named "correct" if any flattened
    expected value (case-insensitive) is a substring of the item's text
    (case-insensitive) — i.e. the item's text contains that expected value.
    If no category is literally named "correct", the item falls back to
    `categories[0]` for this branch.

    Every other item (no flattened expected value found as a substring) is
    classified as the category literally named "wrong". If no category is
    literally named "wrong", the item falls back to `categories[0]` for
    this branch.

    RuleJudge therefore only ever produces two distinct classifications
    regardless of how many categories are supplied — it cannot detect a
    "missing" category or anything more nuanced without semantic
    understanding.
    """

    def __init__(self) -> None:
        pass

    def _flatten_expected(self, expected: dict) -> list[str]:
        flattened: list[str] = []

        def _recurse(obj: object) -> None:
            if isinstance(obj, dict):
                for value in obj.values():
                    _recurse(value)
            elif isinstance(obj, (list, tuple)):
                for value in obj:
                    _recurse(value)
            else:
                flattened.append(str(obj))

        _recurse(expected)
        return flattened

    async def classify(
        self,
        items: list[str],
        categories: list[Category],
        expected: dict,
    ) -> dict[str, str]:
        by_name = {category.name: category.name for category in categories}
        default_name = categories[0].name if categories else "correct"
        correct_name = by_name.get("correct", default_name)
        wrong_name = by_name.get("wrong", default_name)

        expected_values = [v.lower() for v in self._flatten_expected(expected) if v]

        result: dict[str, str] = {}
        for item in items:
            item_lower = item.lower()
            is_match = any(value in item_lower for value in expected_values)
            result[item] = correct_name if is_match else wrong_name
        return result
