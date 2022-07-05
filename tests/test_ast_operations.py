import ast
from typing import cast

from django_to_fastapi.ast_operations import ASTOperation, ASTOperationAction, Runner
from django_to_fastapi.utils import format_string, unparse


def test_ast_operations():
    definition = format_string(
        """def create_post():
    title = request.data.get("title")
"""
    )

    expected = format_string(
        """Payload = TypedDict("Payload", {"title": Any})
def create_post(data: Payload):
    title = data.get("title")
"""
    )

    module = ast.parse(definition)

    function_def = cast(ast.FunctionDef, module.body[0])

    Runner.execute(
        module,
        [
            ASTOperation(
                action=ASTOperationAction.InsertBefore,
                options={
                    "target": function_def,
                    "candidate": ast.Assign(
                        targets=[ast.Name("Payload")],
                        value=ast.Call(
                            func=ast.Name(id="TypedDict"),
                            args=[
                                ast.Constant(value="Payload"),
                                ast.Dict(
                                    keys=[ast.Constant(value="title")],
                                    values=[ast.Name(id="Any")],
                                ),
                            ],
                            keywords=[],
                        ),
                    ),
                },
            ),
        ],
    )

    Runner.insert(
        function_def.args.args,
        target=ast.arg(annotation=ast.Name(id="Payload"), arg="data"),
        position=0,
    )
    ast.fix_missing_locations(function_def)

    root = function_def.body[0].value.func

    operations = [
        ASTOperation(
            action=ASTOperationAction.Replace,
            options={
                "target": root.value,
                "candidate": ast.Name(id=root.value.attr),
            },
        ),
    ]

    Runner.execute(root, operations)

    assert unparse(module) == expected
