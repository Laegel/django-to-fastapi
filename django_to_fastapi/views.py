import ast
from dataclasses import dataclass
from typing import List, Literal, Tuple, cast

from .routes import Route
from .utils import class_name_to_function

HTTP_METHOD = Literal["post", "get", "put", "delete"]


@dataclass
class RouteConfiguration:
    path: str
    method: HTTP_METHOD


def has_function_route_name(node: ast.FunctionDef):
    return node.name in ("post", "get", "put", "delete")


def has_attr_route_name(node: ast.Attribute):
    return node.attr in ("post", "get", "put", "delete")


def is_crud_class(node: ast.ClassDef):
    return (
        len(
            [
                method
                for method in node.body
                if isinstance(method, ast.FunctionDef)
                and has_function_route_name(method)
            ]
        )
        == 4
    )


def has_state(node: ast.ClassDef):
    class Inspect(ast.NodeVisitor):
        def inspect(self, node: ast.ClassDef):
            self.has_state = False
            self.visit(node)

        def visit_Assign(self, node):
            match node:
                case ast.Assign(targets=[ast.Attribute(value=ast.Name(id="self"))]):
                    self.has_state = True
                    return
            return node

    inspector = Inspect()
    inspector.inspect(node)
    return inspector.has_state


def class_to_functions(node: ast.ClassDef, route: Route) -> List[ast.FunctionDef]:
    transformer = ClassToFunctions(route, [])
    transformer.transform(node)
    return transformer.functions


def function_to_function(
    node: ast.FunctionDef, configuration: RouteConfiguration
) -> ast.FunctionDef:
    remover = RemoveArgs(configuration)
    return remover.visit(node)


def class_to_class(node: ast.ClassDef, route: Route) -> ast.ClassDef:
    remover = ClassToClass(route)
    return remover.transform(node)


def get_function_route_method(node: ast.FunctionDef) -> HTTP_METHOD:
    method = (
        next(
            decorator
            for decorator in node.decorator_list
            if isinstance(decorator.func, ast.Name) and decorator.func.id == "api_view"
        )
        .args[0]
        .elts[0]
        .value
    )

    return cast(HTTP_METHOD, method.lower())


class RemoveArgs(ast.NodeTransformer):
    def __init__(self, configuration: RouteConfiguration):
        self.configuration = configuration

    def visit_FunctionDef(self, node):
        new_node = ast.FunctionDef(
            name=node.name,
            args=ast.arguments(posonlyargs=[], args=[], defaults=[], kwonlyargs=[]),
            body=node.body,
            decorator_list=[
                ast.Call(
                    func=ast.Attribute(
                        attr=self.configuration.method, value=ast.Name(id="app")
                    ),
                    args=[ast.Constant(value=self.configuration.path)],
                    keywords=[],
                )
            ],
            returns=node.returns,
        )
        return ast.copy_location(new_node, node)


def recursive(func):
    def wrapper(self, node):
        new_parent_node = func(self, node)

        for field, old_value in ast.iter_fields(new_parent_node):
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, ast.AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(new_parent_node, field)
                else:
                    setattr(new_parent_node, field, new_node)
        return new_parent_node

    return wrapper


class ClassToFunctions(ast.NodeTransformer):
    def __init__(self, route: Route, functions: List[ast.FunctionDef] = []):
        self.route = route
        self.functions = functions

    def transform(self, node: ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self.visit_FunctionDef(cast(ast.FunctionDef, item))
        return

    def _get_attribute_to_name(self, node: ast.Attribute):
        is_route = has_attr_route_name(node)
        name = self._get_route_function_name(node.attr) if is_route else node.attr
        return name

    @recursive
    def visit_Assign(self, node):
        match node:
            case ast.Assign(targets=[ast.Attribute(value=ast.Name(id="self"))]):

                return ast.copy_location(
                    ast.Assign(
                        targets=[
                            ast.Name(id=self._get_attribute_to_name(node.targets[0]))
                        ],
                        value=node.value,
                    ),
                    node,
                )
        return node

    @recursive
    def visit_Attribute(self, node):

        match node:
            case ast.Attribute(value=ast.Name(id="self")):
                return ast.copy_location(
                    ast.Name(id=self._get_attribute_to_name(node)), node
                )

        return node

    @recursive
    def visit_FunctionDef(self, node: ast.FunctionDef):

        is_route = has_function_route_name(node)

        decorator_list = (
            [
                ast.Call(
                    func=ast.Attribute(attr=node.name, value=ast.Name(id="router")),
                    args=[ast.Constant(value=self.route.path)],
                    keywords=[],
                )
            ]
            + cast(List[ast.Call], node.decorator_list)
            if is_route
            else node.decorator_list
        )

        new_node = ast.FunctionDef(
            name=self._get_route_function_name(node.name) if is_route else node.name,
            # args=ast.arguments(posonlyargs=[], args=[], defaults=[], kwonlyargs=[])
            # if is_route
            # else
            args=ast.arguments(
                args=[arg for arg in node.args.args if arg.arg != "self"],
                posonlyargs=node.args.posonlyargs,
                defaults=node.args.defaults,
                kwonlyargs=node.args.kwonlyargs,
            ),
            body=[self.visit(item) for item in node.body],
            decorator_list=decorator_list,
            returns=node.returns,
        )
        self.functions.append(ast.copy_location(new_node, node))
        return node

    def _get_route_function_name(self, name: str):
        return name + "_" + class_name_to_function(self.route.view)

    @recursive
    def visit_ClassDef(self, node):
        return node


class ClassToClass(ast.NodeTransformer):
    def __init__(self, route: Route):
        self.route = route

    def visit_FunctionDef(self, node):

        is_route = has_function_route_name(node)

        decorator_list = (
            [
                ast.Call(
                    func=ast.Attribute(
                        attr=node.name, value=self.get_router_node()
                    ),
                    args=[ast.Constant(value="/")],
                    keywords=[],
                )
            ]
            + cast(List[ast.Call], node.decorator_list)
            if is_route
            else node.decorator_list
        )

        new_node = ast.FunctionDef(
            name=node.name,
            args=ast.arguments(
                args=[arg for arg in node.args.args] if is_route else node.args.args,
                posonlyargs=node.args.posonlyargs,
                defaults=node.args.defaults,
                kwonlyargs=node.args.kwonlyargs,
            ),
            body=node.body,
            decorator_list=decorator_list,
            returns=node.returns,
        )
        return ast.copy_location(new_node, node)

    def transform(self, node):
        node.decorator_list = [
            *node.decorator_list,
            ast.Call(
                func=ast.Name(id="cbv"),
                args=[self.get_router_node()],
                keywords=[],
            ),
        ]
        node.body = [self.visit(item) for item in node.body]

        node.bases = [base for base in node.bases if base.id != "APIView"]

        return node

    def get_router(self):
        return "router_" + class_name_to_function(self.route.view)

    def get_router_node(self):
        return ast.Name(id=self.get_router())
