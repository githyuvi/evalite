"""PipelineScorer: Extractor -> Judge -> Scoring Engine (ADR-007 Decision 3, ADR-008).

`PipelineScorer` is the sophisticated counterpart to `DefaultScorer`
(ADR-007 Decision 4). It wires together an `Extractor`, a `Judge`, and a
weighted scoring formula to turn an agent's free-form response into a
`Score`:

    AS Response -> Extractor -> Judge -> Scoring Engine -> Score

`LLMExtractor` and `LLMJudge` (the defaults) share the single `provider`
instance passed to the constructor, per ADR-008.
"""

from evalite.agent.protocol import AgentResponse
from evalite.llm.provider import LLMProvider
from evalite.runner.result import Score

from .category import DEFAULT_CATEGORIES, Category
from .extractor import Extractor, LLMExtractor
from .judge import Judge, LLMJudge


def _flatten_expected(expected: dict) -> list[str]:
    """Recursively flatten all leaf values in `expected` to strings.

    Mirrors `DefaultScorer._flatten_expected` (evalite/scorer/default.py).
    That method is bound to a `DefaultScorer` instance and not exposed as a
    standalone, importable function, so the same logic is reimplemented
    here as a module-level function rather than reaching into another
    class's instance method.

    Only leaf values are included (dict keys are dropped), each converted
    via `str()`.
    """
    flattened: list[str] = []

    def _recurse(obj: object) -> None:
        if isinstance(obj, dict):
            for value in obj.values():
                _recurse(value)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _recurse(item)
        else:
            flattened.append(str(obj))

    _recurse(expected)
    return flattened


class PipelineScorer:
    """Extractor -> Judge -> Scoring Engine pipeline scorer.

    Satisfies the `Scorer` Protocol (`evalite.scorer.base.Scorer`).

    Wiring (ADR-007 Decision 3/4, ADR-008):
      - `extractor` defaults to `LLMExtractor(provider)` when not supplied.
      - `judge` defaults to `LLMJudge(provider, additional_instructions=...,
        system_prompt=...)` when not supplied. `additional_instructions`
        and `system_prompt` are `LLMJudge`-specific configuration: they are
        only used to construct the default judge. If the caller supplies
        their own `judge` instance (e.g. `RuleJudge()`), those two
        arguments are NOT forwarded to it — a caller-supplied judge is used
        exactly as given.

    Scoring formula (interpretation note — see docstring on `score` for the
    full explanation of how "expected_outcomes" is derived for a generic
    `Scorer`, whose `expected` parameter is a plain `dict`):

        value = clamp(sum(category.weight for each classified item) / len(expected_outcomes), 0.0, 1.0)
        passed = value >= 1.0
    """

    def __init__(
        self,
        provider: LLMProvider,
        categories: list[Category] = DEFAULT_CATEGORIES,
        extractor: Extractor | None = None,
        judge: Judge | None = None,
        additional_instructions: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Build a PipelineScorer.

        Args:
            provider: Shared `LLMProvider` used to construct the default
                `LLMExtractor`/`LLMJudge` when `extractor`/`judge` are not
                supplied (ADR-008: one provider instance, shared).
            categories: Classification buckets with signed weights. Defaults
                to `DEFAULT_CATEGORIES` (correct/wrong/missing).
            extractor: Optional custom `Extractor`. Defaults to
                `LLMExtractor(provider)`.
            judge: Optional custom `Judge`. Defaults to
                `LLMJudge(provider, additional_instructions=additional_instructions,
                system_prompt=system_prompt)`.
            additional_instructions: Appended to the default `LLMJudge`'s
                base system prompt. Only applies when `judge` is not
                supplied (i.e. the default `LLMJudge` is being constructed).
                Ignored if a custom `judge` is supplied.
            system_prompt: Fully replaces the default `LLMJudge`'s base
                system prompt. Only applies when `judge` is not supplied.
                Ignored if a custom `judge` is supplied.
        """
        self._provider = provider
        self._categories = categories
        self._extractor: Extractor = extractor if extractor is not None else LLMExtractor(provider)
        self._judge: Judge = (
            judge
            if judge is not None
            else LLMJudge(
                provider,
                additional_instructions=additional_instructions,
                system_prompt=system_prompt,
            )
        )

    async def score(
        self,
        input: str,
        expected: dict,
        actual: AgentResponse,
    ) -> Score:
        """Score `actual` by running it through the Extractor -> Judge pipeline.

        Pipeline:
          1. `items = await self._extractor.extract(actual.content, expected)`
             — discrete claims/facts pulled from the response.
          2. `classification = await self._judge.classify(items, self._categories, expected)`
             — `{item: category_name}` for each extracted item.
          3. Weighted sum: for every `(item, category_name)` pair in
             `classification`, look up `category_name` in `self._categories`
             and add its `weight` to a running total. Every classified item
             contributes its category's weight, whether positive (reward)
             or negative (penalty).
          4. `value = clamp(weighted_sum / len(expected_outcomes), 0.0, 1.0)`,
             `passed = value >= 1.0`.

        Interpretation note on `expected_outcomes`: `PipelineScorer` is a
        generic `Scorer` and only receives `expected: dict` — there is no
        literal `expected_outcomes` field on this signature (that field
        lives on ADR-007's `ConversationTestCase`, one layer up, and is
        typically passed down packed into this `expected` dict). To resolve
        "what counts as an expected value from an arbitrary dict" the same
        way the rest of the codebase does, this scorer reuses
        `DefaultScorer`'s flattening rule (see `_flatten_expected` in this
        module, mirroring `evalite/scorer/default.py`): `expected`'s values
        are recursively flattened (nested dicts/lists included) into a flat
        list of leaf strings, and `len(expected_outcomes)` is the resulting
        list's length. This makes the denominator consistent with how
        `DefaultScorer` already treats an arbitrary `expected` dict.

        If `expected` flattens to zero values, there is nothing to divide
        by (and no expected outcomes to score against), so this returns
        `Score(passed=False, value=0.0, reasoning="expected dict has no
        values to score against")` rather than raising `ZeroDivisionError`.

        Args:
            input: The input given to the agent (unused directly here; it
                is not needed by the extractor/judge stages, which operate
                on `actual.content` and `expected`).
            expected: Dict of expected values. Flattened per above to
                compute the scoring denominator, and passed through as
                context to the extractor and judge.
            actual: The agent's response.

        Returns:
            A `Score` with `passed`/`value`/`reasoning` set per the formula
            above.
        """
        expected_outcomes = _flatten_expected(expected)
        if len(expected_outcomes) == 0:
            return Score(
                passed=False,
                value=0.0,
                reasoning="expected dict has no values to score against",
            )

        items = await self._extractor.extract(actual.content, expected)
        classification = await self._judge.classify(items, self._categories, expected)

        categories_by_name: dict[str, Category] = {
            category.name: category for category in self._categories
        }

        weighted_sum = 0.0
        counts: dict[str, int] = {}
        for category_name in classification.values():
            category = categories_by_name.get(category_name)
            if category is not None:
                weighted_sum += category.weight
            counts[category_name] = counts.get(category_name, 0) + 1

        raw_value = weighted_sum / len(expected_outcomes)
        value = max(0.0, min(1.0, raw_value))
        passed = value >= 1.0

        counts_summary = ", ".join(f"{name}: {count}" for name, count in counts.items())
        reasoning = f"Classified {len(classification)} items: {{{counts_summary}}}"

        return Score(passed=passed, value=value, reasoning=reasoning)
