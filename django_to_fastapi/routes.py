import ast
from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class Route:
    path: str
    view: str


def get_view(source: str, node: ast.AST):
    if isinstance(node, ast.Call) and node.func.attr == "as_view":
        return (
            node.func.value.id
            if isinstance(node.func.value, ast.Name)
            else node.func.value.func.id
        )

    return ast.get_source_segment(source, node)


class RoutesCollector(ast.NodeVisitor):
    def __init__(self, source: str, routes: List[Route] = []):
        self.source = source
        self.routes = routes

    def visit_Assign(self, node: ast.Assign):
        if node.targets[0].id == "urlpatterns":
            self.routes = [
                Route(
                    path=element.args[0].value,
                    view=get_view(self.source, element.args[1]),
                )
                for element in node.value.elts
            ]


def get_routes(source_code: str) -> Sequence[Route]:
    source_tree = ast.parse(source_code)
    visitor = RoutesCollector(source_code)
    visitor.visit(source_tree)

    return visitor.routes


class ImportsCollector(ast.NodeVisitor):
    def __init__(self, views: List[str], modules: List[str] = []):
        self.views = views
        self.modules = modules

    def visit_Import(self, node: ast.ImportFrom):
        if set(node.names).difference(self.views):
            self.modules.append(node.module)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        try:
            next(node.name for node in node.names if node.name in self.views)
            self.modules.append(node.module)
        except:
            return
            


def get_modules_from_routes(source_code, routes: Sequence[Route]) -> List[str]:
    source_tree = ast.parse(source_code)

    visitor = ImportsCollector([route.view for route in routes])
    visitor.visit(source_tree)
    return [import_.replace(".", "/") for import_ in visitor.modules]
