"""Tests for the Category model and DEFAULT_CATEGORIES (ADR-007 Decision 3)."""

from evalite.scorer.pipeline.category import DEFAULT_CATEGORIES, Category


def test_default_categories_has_exactly_three_entries():
    assert len(DEFAULT_CATEGORIES) == 3


def test_default_categories_names_and_weights():
    by_name = {category.name: category for category in DEFAULT_CATEGORIES}

    assert set(by_name.keys()) == {"correct", "wrong", "missing"}

    assert by_name["correct"].weight == 1.0
    assert by_name["wrong"].weight == -1.0
    assert by_name["missing"].weight == -0.5


def test_default_categories_have_descriptions():
    for category in DEFAULT_CATEGORIES:
        assert isinstance(category.description, str)
        assert category.description


def test_category_is_a_pydantic_model_with_expected_fields():
    category = Category(name="foo", description="bar", weight=0.5)
    assert category.name == "foo"
    assert category.description == "bar"
    assert category.weight == 0.5
