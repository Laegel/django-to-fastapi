import ast
from option import NONE, Some
import pytest

from django_to_fastapi.utils import class_name_to_function, get_arg_or_keyword


@pytest.mark.parametrize(
    ("view", "expected"),
    [
        (
            "PostsView",
            "posts",
        ),
        (
            "UniqueActionView",
            "unique_action",
        ),
    ],
)
def test_class_view_to_function(view: str, expected: str):
    assert class_name_to_function(view) == expected


main_arg = ast.Constant(value="main_arg")
matching_keyword = ast.keyword(arg="status", value=ast.Constant(value=200))

dummy_ast_call = ast.Call(
    func=ast.Name(id="my_function"),
    args=[main_arg],
    keywords=[matching_keyword],
)


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        (
            (dummy_ast_call, "blo", 12),
            NONE,
        ),
        (
            (dummy_ast_call, "status", 1),
            Some(matching_keyword),
        ),
        (
            (dummy_ast_call, "data", 0),
            Some(main_arg),
        ),
    ],
)
def test_get_arg_or_keyword(criteria, expected):
    result = get_arg_or_keyword(*criteria)
    
    assert result.unwrap() == expected.unwrap() if expected.is_some else expected == result
