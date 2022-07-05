import ast
import pytest

from django_to_fastapi.ast_operations import ASTOperation, ASTOperationAction, Runner
from django_to_fastapi.routes import Route
from django_to_fastapi.utils import format_string, unparse
from django_to_fastapi.views import (
    RouteConfiguration,
    class_to_class,
    class_to_functions,
    function_to_function,
    get_function_route_method,
    has_state,
    is_crud_class,
)
from tests.conftest import get_fixture, get_first_node


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

    assert is_crud_class(get_first_node(source_tree)) == expected


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
    assert has_state(get_first_node(definition)) == expected


def test_get_function_route_method():
    definition = get_fixture("route_function.py")
    node = get_first_node(definition)
    assert get_function_route_method(node) == "post"


def test_function_to_function():
    definition = get_fixture("route_function.py")
    expected = '''@router.post("/auth/signin")
def signin():
    """blockcomment"""
    ...
'''

    node = get_first_node(definition)

    (out, _) = function_to_function(
        node, RouteConfiguration(path="/auth/signin", method="post")
    )

    assert unparse(out) == expected


def test_class_to_functions():
    definition = get_fixture("unique_action_class.py")
    expected = """@router.post("/do-something")
def post_unique_action():
    other_method("bla")

def other_method(arg):
    ...
"""

    node = get_first_node(definition)

    functions, _ = class_to_functions(
        node, Route(view="UniqueActionView", path="/do-something")
    )

    assert "\n".join([unparse(node) for node in functions]) == expected


def test_class_to_class():
    definition = get_fixture("crud_class.py")
    node = get_first_node(definition)

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
    out = unparse(class_to_class(node, Route(view="PostsView", path="/posts"))[0])
    assert out == expected


def test_route_io():
    definition = get_fixture("full_route.py")

    expected = format_string(
        """PayloadInputCreatePost = TypedDict("PayloadInputCreatePost", {"title": Any, "content": Optional[Any], "boolean_value": Any, "other_items": Any})

@router.post("/posts")
def create_post(data: PayloadInputCreatePost, blo: str, bli: str, category: Optional[str] = ""):
    title = data.get("title")
    content = data.get("content", "")
    cat = category
    items = do_this({**get_from(("stuff1", "stuff2"), data), "stuff3": "..."})
    if data.get("boolean_value") is not None:
        if data.get("boolean_value") == "":
            boolean_value = None
        else:
            boolean_value = data.get("boolean_value")
    other_items = data["other_items"] if cat == 12 else []
    return Response({ "title": title, "content": content, "category": cat, "blo": blo, "bli": bli })

"""
    )
    module = ast.parse(definition)
    function, operations = function_to_function(
        module.body[0],
        RouteConfiguration(path="/posts", method="post"),
    )

    operations.append(
        ASTOperation(
            action=ASTOperationAction.Replace,
            options={"target": module.body[0], "candidate": function},
        )
    )

    Runner.execute(module, operations)

    out = unparse(module)
    assert out == expected
