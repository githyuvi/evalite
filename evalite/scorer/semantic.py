"""Semantic similarity scorer for evalite.

Compares actual.content against expected's flattened values using
sentence embeddings, and passes if the maximum cosine similarity meets
a threshold.

This scorer has an optional dependency on `sentence-transformers`,
which is not a project dependency of evalite itself. Install it with
`pip install evalite[semantic]` to use this scorer.
"""

from evalite.agent.protocol import AgentResponse
from evalite.runner.result import Score


class SemanticSimilarityScorer:
    """
    Compares actual.content to expected's flattened values using sentence
    embeddings. Passes if the maximum cosine similarity between
    actual.content and any flattened expected value meets `threshold`.
    Score.value = max cosine similarity, clamped to [0.0, 1.0].
    """

    def __init__(
        self, threshold: float = 0.8, model_name: str = "all-MiniLM-L6-v2"
    ) -> None:
        """Initialize the scorer and load the sentence embedding model.

        Args:
            threshold: Minimum cosine similarity required to pass.
            model_name: Name of the sentence-transformers model to load.

        Raises:
            ImportError: If sentence-transformers is not installed.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "SemanticSimilarityScorer requires sentence-transformers: "
                "pip install evalite[semantic]"
            ) from e

        self.threshold = threshold
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def _flatten_expected(self, expected: dict) -> list[str]:
        """Recursively flatten all leaf values in expected dict to strings.

        Only leaf values are included (no dict keys), converted to str().

        Args:
            expected: The expected dict, possibly nested.

        Returns:
            A list of string values from all leaves in the dict.
        """
        flattened = []

        def _recurse(obj):
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

    async def score(
        self,
        input: str,
        expected: dict,
        actual: AgentResponse,
    ) -> Score:
        """Score the actual response against expected values by semantic similarity.

        Computes the cosine similarity between the embedding of
        actual.content and the embedding of each flattened expected value,
        and takes the maximum.

        Args:
            input: The input given to the agent (unused for this scorer).
            expected: Dict of expected values. Nested dicts are flattened.
            actual: The agent's response.

        Returns:
            A Score with passed/value/reasoning.
        """
        import numpy as np

        flattened = self._flatten_expected(expected)

        if not flattened:
            return Score(
                passed=True, value=1.0, reasoning="0 expected values to compare"
            )

        actual_embedding = self.model.encode([actual.content])[0]
        expected_embeddings = self.model.encode(flattened)

        actual_norm = actual_embedding / np.linalg.norm(actual_embedding)
        similarities = []
        for expected_embedding in expected_embeddings:
            expected_norm = expected_embedding / np.linalg.norm(expected_embedding)
            similarities.append(float(np.dot(actual_norm, expected_norm)))

        max_similarity = max(similarities)
        value = max(0.0, min(1.0, max_similarity))
        passed = max_similarity >= self.threshold

        reasoning = f"max cosine similarity {max_similarity:.4f} (threshold {self.threshold})"

        return Score(passed=passed, value=value, reasoning=reasoning)
