from evalite.testcase.conversation import ConversationTestCase


class FakeDriver:
    """Minimal fake satisfying the `ConversationDriver` Protocol structurally
    (Protocol conformance is duck-typed, not declared via inheritance)."""

    async def next_message(self, history: list[dict], response: str) -> str:
        return "sounds good"

    async def should_continue(self, history: list[dict], response: str) -> bool:
        return False


def test_valid_construction_with_driver():
    case = ConversationTestCase(
        id="book_room_001",
        initial_message="I need to book a meeting room for tomorrow at 3pm",
        expected_outcomes=["room booked", "confirmation sent"],
        driver=FakeDriver(),
    )

    assert case.driver is not None
    assert case.turn_inputs is None


def test_valid_construction_with_turn_inputs():
    case = ConversationTestCase(
        id="book_room_002",
        initial_message="I need to book a meeting room for tomorrow at 3pm",
        expected_outcomes=["room booked"],
        turn_inputs=["yes that works", "thanks"],
    )

    assert case.driver is None
    assert case.turn_inputs == ["yes that works", "thanks"]


def test_valid_construction_with_neither_driver_nor_turn_inputs():
    # Neither provided is valid, not an error — it means a single
    # follow-up turn (ADR-007, Decision 1).
    case = ConversationTestCase(
        id="book_room_003",
        initial_message="I need to book a meeting room for tomorrow at 3pm",
        expected_outcomes=["room booked"],
    )

    assert case.driver is None
    assert case.turn_inputs is None


def test_accumulator_and_accumulate_both_provided_does_not_raise():
    # Precedence between `accumulate` and `accumulator` (accumulator wins
    # when both are given) is resolved by the runner at execution time,
    # not by this model. This model's only job is to accept and store
    # both fields as given without validating their interaction.
    custom_accumulator = object()

    case = ConversationTestCase(
        id="book_room_004",
        initial_message="I need to book a meeting room for tomorrow at 3pm",
        expected_outcomes=["room booked"],
        accumulate=True,
        accumulator=custom_accumulator,
    )

    assert case.accumulate is True
    assert case.accumulator is custom_accumulator


def test_defaults():
    case = ConversationTestCase(
        id="book_room_005",
        initial_message="I need to book a meeting room for tomorrow at 3pm",
        expected_outcomes=["room booked"],
    )

    assert case.scorer is None
    assert case.accumulate is False
    assert case.accumulator is None
    assert case.max_turns == 10
    assert case.iterations == 1
    assert case.timeout_per_turn is None
    assert case.tags == []
