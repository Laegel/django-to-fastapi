import ast
from enum import Enum
from typing import List, Sequence
from django_to_fastapi.ast_operations import (
    ASTOperation,
    ASTOperationAction,
    ASTOperations,
    Runner,
)

from django_to_fastapi.routes import Route
from django_to_fastapi.utils import class_name_to_function, format_string
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
    migrator = Migrator(routes)
    migrator.visit(module)
    Runner.execute(module, migrator.operations)
    return module


def _clear_imports(module: ast.Module):
    remover = RemoveImports()
    return remover.visit(module)


def process_code(source_code: str, routes: Sequence[Route]):
    source_tree = ast.parse(source_code)
    migrated = _migrate(source_tree, routes)
    return _clear_imports(migrated)


class RemoveImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        if node.module == "django.conf":
            return ast.copy_location(
                ast.ImportFrom(
                    module="conf",
                    level=0,
                    names=[ast.alias(name="settings", asname=None)],
                ),
                node,
            )
        return None if self._is_django_import(node.module) else node

    def visit_Import(self, node):
        return None if self._is_django_import(node.names[0].name) else node

    def _is_django_import(self, module: str):
        return next(
            (True for package in DJANGO_PACKAGES if module.startswith(package)),
            False,
        )


class FastAPIUtilsImports(Enum):
    ClassBasedView = 0
    InferringRouter = 1
    Router = 2
    Types = 3
    CommonImports = 4


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
        FastAPIUtilsImports.Types: ast.ImportFrom(
            level=0,
            module="typing",
            names=[
                ast.alias(name="TypedDict", asname=None),
                ast.alias(name="Any", asname=None),
            ],
        ),
        FastAPIUtilsImports.CommonImports: ast.ImportFrom(
            level=0,
            module="fastapi",
            names=[
                ast.alias(name="Response", asname=None),
                ast.alias(name="Request", asname=None),
                ast.alias(name="Depends", asname=None),
            ],
        ),
    }[import_kind]


class Migrator(ast.NodeVisitor):
    def __init__(self, routes: Sequence[Route]):
        self.routes = routes
        self.operations: ASTOperations = []

    def visit_Module(self, node):
        additional_imports = set()
        routers = []

        def add_main_router(target):
            routers.append("router")
            sub_router = ast.Assign(
                targets=[ast.Name(id="router")],
                value=ast.Call(
                    func=ast.Name(id="InferringRouter"),
                    args=[],
                    keywords=[],
                ),
            )
            self.operations.append(
                ASTOperation(
                    action=ASTOperationAction.InsertBefore,
                    options={"target": target, "candidate": sub_router},
                )
            )

        for item in node.body:

            try:
                matching_route = next(
                    route for route in self.routes if route.view == item.name
                )
            except:
                continue

            match item:
                case ast.ClassDef():
                    out, operations = self._handle_class(item, matching_route)
                    match out:
                        case [*functions]:

                            if "router" not in routers:
                                add_main_router(item)
                                additional_imports.add(
                                    FastAPIUtilsImports.ClassBasedView
                                )
                                additional_imports.add(
                                    FastAPIUtilsImports.InferringRouter
                                )
                                additional_imports.add(FastAPIUtilsImports.Types)
                                additional_imports.add(
                                    FastAPIUtilsImports.CommonImports
                                )

                            self.operations += [
                                ASTOperation(
                                    ASTOperationAction.InsertBefore,
                                    options={
                                        "target": item,
                                        "candidate": function_def,
                                    },
                                )
                                for function_def in functions
                            ]

                            self.operations += operations

                            self.operations.append(
                                ASTOperation(
                                    ASTOperationAction.Remove,
                                    options={
                                        "target": item,
                                    },
                                )
                            )

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
                            routers.append(sub_router_name)

                            self.operations.append(
                                ASTOperation(
                                    action=ASTOperationAction.InsertBefore,
                                    options={"target": item, "candidate": sub_router},
                                )
                            )

                            self.operations += operations

                            self.operations += [
                                ASTOperation(
                                    ASTOperationAction.Replace,
                                    options={
                                        "target": item,
                                        "candidate": out,
                                    },
                                )
                            ]

                            # items.append(out)

                            additional_imports.add(FastAPIUtilsImports.ClassBasedView)
                            additional_imports.add(FastAPIUtilsImports.InferringRouter)
                            additional_imports.add(FastAPIUtilsImports.Types)
                            additional_imports.add(FastAPIUtilsImports.CommonImports)

                case ast.FunctionDef():
                    if "router" not in routers:
                        add_main_router(item)
                        additional_imports.add(FastAPIUtilsImports.InferringRouter)
                        additional_imports.add(FastAPIUtilsImports.Types)
                        additional_imports.add(FastAPIUtilsImports.CommonImports)
                    out, operations = self._handle_function(item, matching_route)
                    self.operations += operations
                    self.operations += [
                        ASTOperation(
                            ASTOperationAction.Replace,
                            options={
                                "target": item,
                                "candidate": out,
                            },
                        )
                    ]

        for additional_import in additional_imports:
            # items.insert(0, _resolve_import(additional_import))
            self.operations.append(
                ASTOperation(
                    action=ASTOperationAction.InsertAfter,
                    options={
                        "target": next(
                            importnode
                            for importnode in reversed(node.body)
                            if isinstance(importnode, (ast.ImportFrom, ast.Import))
                        ),
                        "candidate": _resolve_import(additional_import),
                    },
                )
            )

        self.operations.append(
            ASTOperation(
                action=ASTOperationAction.InsertLast,
                options={
                    "target": ast.Assign(
                        targets=[ast.Name(id="routers")],
                        value=ast.List(
                            elts=[ast.Name(id=id) for id in routers],
                        ),
                    )
                },
            )
        )

        return node

    def _handle_class(self, node, matching_route):
        return (
            class_to_class(node, matching_route)
            if is_crud_class(node) or has_state(node)
            else class_to_functions(node, matching_route)
        )

    def _handle_function(self, node, matching_route):
        route_configuration = RouteConfiguration(
            matching_route.path,
            next(decorator for decorator in node.decorator_list)
            .args[0]
            .elts[0]
            .value.lower(),
        )

        return function_to_function(node, route_configuration)


def generate_bootstrap_module():
    return format_string(
        """from os import getenv

from fastapi import FastAPI

CONTEXT = getenv("CONTEXT", "prod")


def create_app():
    if CONTEXT == "dev":
        return FastAPI()
    else:
        return FastAPI(docs_url="/debug", redoc_url=None)


app = create_app()
"""
    )


def generate_entrypoint():

    return format_string(
        f"""import os
import glob
import importlib.util

import uvicorn

from bootstrap import app, CONTEXT

root = os.path.dirname(__file__)

files = [f for f in glob.glob(root + "**/*.py", recursive=True)]

for module_name in files:
    name = module_name.split("/")[0]
    spec = importlib.util.spec_from_file_location(name, module_name)
    module = importlib.util.module_from_spec(spec)
    routers = getattr(module, "routers", [])
    for router in routers:
        app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="127.0.0.1", port=4000, log_level="error", reload=CONTEXT == "dev"
    )
"""
    )
