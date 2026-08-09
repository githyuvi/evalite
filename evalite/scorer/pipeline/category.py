"""Category model for PipelineScorer classification (ADR-007 Decision 3).

A `Category` is a named bucket that an extracted item can be classified
into, carrying a `weight` used by the scoring engine to turn a set of
classified items into a numeric score. Weights may be positive (reward)
or negative (penalty).
"""

from pydantic import BaseModel


class Category(BaseModel):
    """A single classification bucket for PipelineScorer.

    Attributes:
        name: Short identifier for the category (e.g. "correct").
        description: Human-readable description fed to the LLM judge's
            system prompt so it knows what belongs in this category.
        weight: Signed weight applied by the scoring engine. Positive
            weights reward, negative weights penalize.
    """

    name: str
    description: str
    weight: float


DEFAULT_CATEGORIES: list[Category] = [
    Category(
        name="correct",
        description="Factually correct, matches expected outcomes",
        weight=1.0,
    ),
    Category(
        name="wrong",
        description="Factually incorrect or contradicts expected",
        weight=-1.0,
    ),
    Category(
        name="missing",
        description="Expected information absent from response",
        weight=-0.5,
    ),
]
