"""Smoke tests for example files — verify they are parseable Python."""

import ast
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _example_files():
    """Collect all .py files in the examples directory."""
    if not EXAMPLES_DIR.is_dir():
        return []
    return sorted(EXAMPLES_DIR.glob("*.py"))


@pytest.mark.parametrize("example_file", _example_files(), ids=lambda p: p.name)
def test_example_parses(example_file):
    """Each example file should be valid Python (parseable by ast.parse)."""
    source = example_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(example_file))
    assert tree is not None
    # Verify it has at least some content (not empty)
    assert len(tree.body) > 0
