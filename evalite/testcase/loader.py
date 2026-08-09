from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from evalite.testcase.models import TestSet


def load_test_set(path: str | Path) -> TestSet:
    """
    Loads and validates a YAML file into a TestSet.
    Raises ValueError with file path + field name + reason on any validation error.
    Never raises a raw Pydantic ValidationError to the user.
    """
    path = Path(path)

    with open(path) as f:
        data = yaml.safe_load(f)

    # Check if loaded YAML is a dict
    if not isinstance(data, dict):
        raise ValueError(f"Invalid test set at {path}: expected a mapping at the top level")

    # Try to parse into TestSet
    try:
        return TestSet(**data)
    except ValidationError as exc:
        # Extract the first error
        error = exc.errors()[0]
        field = ".".join(str(loc) for loc in error["loc"])
        reason = error["msg"]
        raise ValueError(f"Invalid test set at {path}: field '{field}' — {reason}")
