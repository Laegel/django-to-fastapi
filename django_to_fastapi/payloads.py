import ast
from typing import Dict, List, Tuple, Optional

from option import NONE, Some, Option
from django_to_fastapi.ast_operations import (
    ASTOperation,
    ASTOperationAction,
    ASTOperations,
    Runner,
    find_field,
)

from django_to_fastapi.utils import to_pascal_case, unparse, Logger


def get_payload_inputs(node: ast.FunctionDef, context: Optional[str] = ""):
    visitor = InputCollector(context)
    return visitor.collect(node)


class InputCollector(ast.NodeVisitor):
    def __init__(self, context: Optional[str] = ""):
        self.args: Dict[str, Tuple[Option[ast.AST], Option[ast.AST]]] = {}
        self.context = context
        self.body_input: Option[Dict[str, ast.AST]] = NONE
        self.operations: ASTOperations = []
        self.otherops: List[Tuple[ast.AST, ASTOperation]] = []

    def visit_Name(self, node):
        if node.id != "request":
            return node

        def get_final_node(root, child):
            field = find_field(root, child)
            if not field:
                return get_final_node(root.parent, root)
            if (
                isinstance(getattr(root, field), list)
                or isinstance(root, ast.Assign)
                or isinstance(root, ast.IfExp)
            ):
                return child
            return get_final_node(root.parent, root)

        def walk_until_parent_is_not(node, target_class):
            if not isinstance(node.parent, target_class):
                return node.parent
            else:
                return walk_until_parent_is_not(node.parent, target_class)

        def walk_until_parent_is(node, target_class):
            if isinstance(node.parent, target_class):
                return node
            else:
                return walk_until_parent_is(node.parent, target_class)

        def wrap(items: list, index: int):
            try:
                return Some(items[index])
            except IndexError:
                return NONE

        def handle_final(node: ast.AST):
            match node:
                case ast.Call(
                    func=ast.Attribute(
                        attr="get",
                        value=ast.Attribute(attr="data", value=ast.Name(id="request")),
                    )
                ):
                    return node.args[0].value, wrap(node.args, 1)
                case ast.Call():
                    return node.args[0].value, wrap(node.args, 1)
                case ast.Assign():
                    return node.value.slice.value, NONE
                case ast.Subscript():
                    return node.slice.value, NONE
                case _:
                    return node.args[0].value, NONE

        try:
            match node.parent:
                case ast.Attribute():
                    match node.parent.attr:
                        case "data":
                            final = get_final_node(node.parent.parent, node.parent)
                            if final.parent is self.root:
                                self.body_input = Some({})
                            elif final is node.parent:
                                self.body_input = Some(self.body_input.unwrap_or({}))
                                Runner.replace(
                                    node.parent.parent, node.parent, ast.Name(id="data")
                                )
                                ast.fix_missing_locations(node.parent.parent)
                            else:
                                body_input_definitions = self.body_input.unwrap_or({})
                                name, default = handle_final(final)

                                body_input_definitions[name] = (
                                    ast.Subscript(
                                        slice=ast.Name(id="Any"),
                                        value=ast.Name(id="Optional"),
                                    )
                                    if default.is_some
                                    else ast.Name(id="Any")
                                )

                                self.body_input = Some(body_input_definitions)

                                Runner.replace(
                                    node.parent.parent, node.parent, ast.Name(id="data")
                                )
                                ast.fix_missing_locations(node.parent.parent)

                        case "query_params" | "GET":
                            final = walk_until_parent_is_not(node.parent, ast.Attribute)
                            name, default = handle_final(final)
                            self.args[name] = (
                                default,
                                Some(
                                    ast.Subscript(
                                        slice=ast.Name(id="str"),
                                        value=ast.Name(id="Optional"),
                                    )
                                    if default.is_some
                                    else ast.Name(id="str")
                                ),
                            )

                            match final.parent:
                                case ast.Assign():
                                    if final.parent.targets[0].id == name:
                                        self.otherops.append(
                                            (
                                                final.parent.parent,
                                                ASTOperation(
                                                    action=ASTOperationAction.Remove,
                                                    options={"target": final.parent},
                                                ),
                                            )
                                        )
                                    else:
                                        Runner.replace(
                                            final.parent, final, ast.Name(id=name)
                                        )
                                        ast.fix_missing_locations(final.parent)
                                case ast.Call():
                                    ...
                                case _:
                                    Runner.replace(
                                        final.parent, final, ast.Name(id=name)
                                    )
                                    ast.fix_missing_locations(final.parent)
                        case str:
                            
                            self.args[node.parent.attr] = (
                                Some(
                                    ast.Call(
                                        func=ast.Name(id="Depends"),
                                        args=[ast.Name(id="get_" + node.parent.attr)],
                                        keywords=[],
                                    )
                                ),
                                Some(ast.Name(id="Any")),
                            )
                            Runner.replace(
                                node.parent.parent, node.parent, ast.Name(id=node.parent.attr)
                            )
                            ast.fix_missing_locations(node.parent.parent)
        except Exception as e:
            Logger.print_warn(
                f"Could not handle request rewrite: ({e})",
                sample_code=unparse(walk_until_parent_is(node.parent, ast.FunctionDef)),
                line=node.lineno,
            )

        if self.body_input.is_some and "data" not in self.args:
            self.args["data"] = (NONE, Some(ast.Name(id=self.get_payload_input())))

        return node

    def get_payload_input(self):
        return "PayloadInput" + self.context + to_pascal_case(self.root.name)

    def collect(self, node: ast.FunctionDef):
        self.root = node
        for item in ast.walk(node):
            for child in ast.iter_child_nodes(item):
                child.parent = item

        [self.visit(item) for item in node.body]

        Runner.execute(node, self.operations)
        for (root, operation) in self.otherops:
            Runner.execute(root, [operation])

        return [(key, *value) for key, value in sorted(self.args.items(), key=lambda value: value[1][0].is_some)], Some(
            self._define_payload_type()
        ) if "data" in self.args else NONE

    def _define_payload_type(self):
        keys = [ast.Constant(value=key) for key in self.body_input.unwrap().keys()]
        values = [value for value in self.body_input.unwrap().values()]

        return ast.Assign(
            targets=[ast.Name(id=self.get_payload_input())],
            value=ast.Call(
                func=ast.Name(id="TypedDict"),
                args=[
                    ast.Constant(value=self.get_payload_input()),
                    ast.Dict(keys=keys, values=values),
                ],
                keywords=[],
            ),
        )
