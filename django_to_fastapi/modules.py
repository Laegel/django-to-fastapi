import ast
from enum import Enum
from typing import Sequence

from django_to_fastapi.routes import Route
from django_to_fastapi.utils import class_name_to_function
from django_to_fastapi.views import (
    RouteConfiguration,
    class_to_class,
    class_to_functions,
    function_to_function,
    has_state,
    is_crud_class,
)

DJANGO_PACKAGES = ("rest_framework", "django")


def _migrate(module: ast.Module, routes: Sequence[Route]):
    remover = Migrator(routes)
    return remover.visit(module)


def _clear_imports(module: ast.Module):
    remover = RemoveImports()
    return remover.visit(module)


def process_code(source_code: str, routes: Sequence[Route]):
    source_tree = ast.parse(source_code)
    migrated = _migrate(source_tree, routes)
    return _clear_imports(migrated)


class RemoveImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return None if self._is_django_import(node.module) else node

    def visit_Import(self, node):
        return None if self._is_django_import(node.names[0].name) else node

    def _is_django_import(self, module: str):
        return next(
            (True for package in DJANGO_PACKAGES if module.startswith(package)),
            False,
        )


class FastAPIUtilsImports(Enum):
    ClassBasedView = (0,)
    InferringRouter = (1,)
    Router = 2


def _resolve_import(import_kind: FastAPIUtilsImports):
    return {
        FastAPIUtilsImports.ClassBasedView: ast.ImportFrom(
            level=0,
            module="fastapi_utils.cbv",
            names=[ast.alias(name="cbv", asname=None)],
        ),
        FastAPIUtilsImports.InferringRouter: ast.ImportFrom(
            level=0,
            module="fastapi_utils.inferring_router",
            names=[ast.alias(name="InferringRouter", asname=None)],
        ),
        FastAPIUtilsImports.Router: ast.ImportFrom(
            level=0,
            module="fastapi_utils.router",
            names=[ast.alias(name="Router", asname=None)],
        ),
    }[import_kind]


class Migrator(ast.NodeTransformer):
    def __init__(self, routes: Sequence[Route]):
        self.routes = routes

    def visit_Module(self, node):
        additional_imports = set()
        items = []
        routers = []

        def add_main_router():
            routers.append("router")
            sub_router = ast.Assign(
                targets=[ast.Name(id="router")],
                value=ast.Call(
                    func=ast.Name(id="InferringRouter"),
                    args=[],
                    keywords=[],
                ),
            )
            items.append(sub_router)

        for item in node.body:
            match item:
                case ast.ClassDef():
                    out = self.visit_ClassDef(item)
                    match out:
                        case [*functions]:
                            if "router" not in routers:
                                add_main_router()
                            items += functions

                        case ast.ClassDef():
                            sub_router_name = "router_" + class_name_to_function(
                                out.name
                            )
                            sub_router = ast.Assign(
                                targets=[ast.Name(id=sub_router_name)],
                                value=ast.Call(
                                    func=ast.Name(id="InferringRouter"),
                                    args=[],
                                    keywords=[],
                                ),
                            )
                            items.append(sub_router)
                            routers.append(sub_router_name)

                            items.append(out)

                            additional_imports.add(FastAPIUtilsImports.ClassBasedView)
                            additional_imports.add(FastAPIUtilsImports.InferringRouter)

                case ast.FunctionDef():
                    if "router" not in routers:
                        add_main_router()
                    items.append(self.visit_FunctionDef(item))
                case _:
                    items.append(item)

        for additional_import in additional_imports:
            items.insert(0, _resolve_import(additional_import))
        items.append(
            ast.Assign(
                targets=[ast.Name(id="routers")],
                value=ast.Dict(
                    keys=[ast.Constant(value=value) for value in routers],
                    values=[ast.Name(id=id) for id in routers],
                ),
            )
        )

        node.body = items
        ast.fix_missing_locations(node)
        return node

    def visit_ClassDef(self, node):
        try:
            matching_route = next(
                route for route in self.routes if route.view == node.name
            )
        except StopIteration:
            return node

        if is_crud_class(node) or has_state(node):
            return class_to_class(node, matching_route)
        else:
            return class_to_functions(node, matching_route)

    def visit_FunctionDef(self, node):
        try:
            matching_route = next(
                route for route in self.routes if route.view == node.name
            )
        except StopIteration:
            return node

        route_configuration = RouteConfiguration(
            matching_route.path,
            next(decorator for decorator in node.decorator_list)
            .args[0]
            .elts[0]
            .value.lower(),
        )

        return function_to_function(node, route_configuration)
