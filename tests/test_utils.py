import pytest

from django_to_fastapi.utils import class_name_to_function


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
