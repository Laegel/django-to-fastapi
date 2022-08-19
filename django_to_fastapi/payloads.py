import ast
import json
from typing import Dict, List, Literal, Tuple, Optional

from option import NONE, Some, Option
from django_to_fastapi.ast_operations import (
    ASTOperation,
    ASTOperationAction,
    ASTOperations,
    Runner,
    find_field,
)

from django_to_fastapi.utils import get_arg_or_keyword, to_pascal_case, unparse, Logger


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
        self.out = []

    def visit_Name(self, node):
        if node.id == "Response" and isinstance(node.parent, ast.Call):
            return self._handle_response(node)
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
                                node.parent.parent,
                                node.parent,
                                ast.Name(id=node.parent.attr),
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

    def get_payload_output(self):
        return "PayloadOutput" + self.context + to_pascal_case(self.root.name)

    def collect(self, node: ast.FunctionDef):
        self.root = node
        for item in ast.walk(node):
            for child in ast.iter_child_nodes(item):
                child.parent = item

        [self.visit(item) for item in node.body]

        Runner.execute(node, self.operations)
        for (root, operation) in self.otherops:
            Runner.execute(root, [operation])

        return (
            [
                (key, *value)
                for key, value in sorted(
                    self.args.items(), key=lambda value: value[1][0].is_some
                )
            ],
            Some(self._define_payload_type()) if "data" in self.args else NONE,
            Some(self._define_payload_output()) if self.out else NONE,
        )

    def _define_payload_type(self):
        keys = [ast.Constant(value=key) for key in self.body_input.unwrap().keys()]
        values = [value for value in self.body_input.unwrap().values()]

        payload_type_name = self.get_payload_input()

        return ast.Assign(
            targets=[ast.Name(id=payload_type_name)],
            value=ast.Call(
                func=ast.Name(id="TypedDict"),
                args=[
                    ast.Constant(value=payload_type_name),
                    ast.Dict(keys=keys, values=values),
                ],
                keywords=[],
            ),
        )

    def _define_payload_output(self):
        def get_type(item, context=""):
            match item:
                case ast.Name():
                    # return type(item.id).__name__
                    return ast.Name(id=type(item.id).__name__), type(item.id).__name__
                case ast.Constant():
                    # return type(item.value).__name__
                    return (
                        ast.Name(id=type(item.value).__name__),
                        type(item.value).__name__,
                    )
                case ast.Dict():
                    # return "dict"
                    values, identifiers = list(
                        zip(*[get_type(value) for value in item.values])
                    )
                    return ast.Call(
                        args=[
                            ast.Constant(value=context),
                            ast.Dict(keys=item.keys, values=values),
                        ],
                        func=ast.Name(id="TypedDict"),
                        keywords=[],
                    ), "dict:" + ",".join(identifiers)
                case ast.JoinedStr():
                    # return "str"
                    return ast.Name(id="str"), "str"
                case ast.Attribute():
                    # return "str"
                    return ast.Name(id="str"), "str"
                case ast.ListComp() | ast.List():
                    # return "list"
                    return ast.Name(id="list"), "list"
                case _:
                    # return "Any"
                    return ast.Name(id="Any"), "Any"

        types = []
        types_indexer = set()

        for item in self.out:
            temp_type, identifier = get_type(item, self.get_payload_output())
            if identifier not in types_indexer:
                types.append(temp_type)
                types_indexer.add(identifier)
            if identifier.startswith("dict"):
                types = [temp_type]
                break

        if len(types) > 1:
            value = ast.Subscript(
                slice=ast.Tuple(elts=[item for item in types]),
                value=ast.Name(id="Union"),
            )
        else:
            value = types[0]

        return ast.Assign(targets=[ast.Name(id=self.get_payload_output())], value=value)

    def _handle_response(self, node: ast.Name):

        payload = get_arg_or_keyword(node.parent, "data", 0)

        status = get_arg_or_keyword(node.parent, "status", 1)

        def getnewwcall(status_node: ast.AST, payload):
            return ast.Call(
                func=ast.Name("JSONResponse"),
                args=[payload.unwrap()] if payload.is_some else [ast.Constant(value="")],
                keywords=[
                    ast.keyword(
                        arg="status_code", value=status_node
                    )
                ],
            )

        def handle_target(status_code, status_value, payload):
            if payload.is_some:
                self.out.append(payload.unwrap())
            return (
                getnewwcall(status_value, payload)
                if status_code != 200 or status_code == 200 and payload.is_none
                else payload.unwrap()
            )

        if status.is_some:
            status_node = status.unwrap()
            status_value = (
                status_node.value
                if isinstance(status_node, ast.keyword)
                else status_node
            )
            match status_value:
                case ast.Attribute():
                    if status_value.attr.startswith("HTTP_"):
                        status_code = int(status_value.attr.split("_")[1])
                        target = handle_target(status_code, status_value, payload)
                case ast.Constant(value=status_code):
                    target = handle_target(status_code, status_value, payload)
                case _:
                    ...
        else:
            target = payload.unwrap()
        Runner.replace(node.parent.parent, node.parent, target)
        ast.fix_missing_locations(node.parent.parent)
        return node
