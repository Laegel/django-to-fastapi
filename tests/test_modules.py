import ast

from django_to_fastapi.modules import _clear_imports
from django_to_fastapi.utils import unparse
from tests.conftest import get_fixture


def test_clear_imports():
    definition = get_fixture("imports.py")

    source_tree = ast.parse(definition)
    assert unparse(_clear_imports(source_tree)) == "from re import sub\n"
