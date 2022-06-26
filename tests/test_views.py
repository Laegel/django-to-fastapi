import ast
import pytest

from django_to_fastapi.routes import Route
from django_to_fastapi.utils import unparse
from django_to_fastapi.views import (
    RouteConfiguration,
    class_to_class,
    class_to_functions,
    function_to_function,
    get_function_route_method,
    has_state,
    is_crud_class,
)
from tests.conftest import get_fixture


def _get_first_node(source_code: str):
    source_tree = ast.parse(source_code)
    return source_tree.body[0]


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        (
            get_fixture("crud_class.py"),
            True,
        ),
        (
            get_fixture("unique_action_class.py"),
            False,
        ),
        (
            get_fixture("route_function.py"),
            False,
        ),
    ],
)
def test_is_crud_class(definition: str, expected: bool):
    source_tree = ast.parse(definition)

    assert is_crud_class(_get_first_node(source_tree)) == expected


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        (
            get_fixture("stateful_class.py"),
            True,
        ),
        (
            get_fixture("unique_action_class.py"),
            False,
        ),
    ],
)
def test_has_state(definition: str, expected: bool):
    assert has_state(_get_first_node(definition)) == expected


def test_get_function_route_method():
    definition = get_fixture("route_function.py")
    node = _get_first_node(definition)
    assert get_function_route_method(node) == "post"


def test_function_to_function():
    definition = get_fixture("route_function.py")
    expected = '''@app.post("/auth/signin")
def signin():
    """blockcomment"""
    ...
'''

    node = _get_first_node(definition)

    assert (
        unparse(
            function_to_function(
                node, RouteConfiguration(path="/auth/signin", method="post")
            )
        )
        == expected
    )


def test_class_to_functions():
    definition = get_fixture("unique_action_class.py")
    expected = """@router.post("/do-something")
def post_unique_action(arg):
    ...

def other_method():
    post_unique_action("bla")
"""

    node = _get_first_node(definition)

    assert (
        "\n".join(
            [
                unparse(node)
                for node in class_to_functions(
                    node, Route(view="UniqueActionView", path="/do-something")
                )
            ]
        )
        == expected
    )


def test_class_to_class():
    definition = get_fixture("crud_class.py")
    node = _get_first_node(definition)

    expected = """@cbv(router_posts)
class PostsView:
    @router_posts.get("/")
    def get(self):
        ...

    @router_posts.post("/")
    def post(self):
        ...

    @router_posts.put("/")
    def put(self):
        ...

    @router_posts.delete("/")
    def delete(self):
        ...
"""
    assert (
        unparse(class_to_class(node, Route(view="PostsView", path="/posts")))
        == expected
    )
