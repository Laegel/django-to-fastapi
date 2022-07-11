import ast

from option import NONE, Some
import pytest

from django_to_fastapi.payloads import get_payload_inputs
from django_to_fastapi.utils import unparse
from tests.conftest import get_first_node


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        (
            "prop = request.prop",
            [
                (
                    "prop",
                    Some(ast.Call),
                    Some(ast.Name(id="Any")),
                )
            ],
        ),
        (
            """category = request.query_params.get("category")""",
            [("category", NONE, Some(ast.Name(id="str")))],
        ),
        (
            """posts = request.data["posts"]""",
            [("data", NONE, Some(ast.Name(id="PayloadInputMyView")))],
        ),
        (
            """comments = request.data.get("comments")""",
            [("data", NONE, Some(ast.Name(id="PayloadInputMyView")))],
        ),
        (
            """comments = request.data.get("comments", [])""",
            [("data", NONE, Some(ast.Name(id="PayloadInputMyView")))],
        ),
        (
            """data = request.data""",
            [("data", NONE, Some(ast.Name(id="PayloadInputMyView")))],
        ),
    ],
)
def test_get_payload_inputs(definition: str, expected):

    definition = f"""def my_view():
    {definition}
    """

    inputs, _, _ = get_payload_inputs(get_first_node(definition))

    if not inputs:
        assert inputs == expected
    else:
        for index, (name, default, annotation) in enumerate(inputs):

            assert name == expected[index][0]

            assert (
                isinstance(default.unwrap(), expected[index][1].unwrap())
                if default.is_some
                else default == expected[index][1]
            )

            assert annotation.unwrap().id == expected[index][2].unwrap().id


def test_get_payload_outputs():
    definition = f"""def my_view():
    return Response("bla", status=status.HTTP_200_OK)
    """

    module = ast.parse(definition)

    node = module.body[0]
    _, _, payload_output = get_payload_inputs(node)

    assert payload_output.unwrap().targets[0].id == "PayloadOutputMyView"
    assert payload_output.unwrap().value.id == "str"