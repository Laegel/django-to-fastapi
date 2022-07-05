import ast
from os import path


FIXTURES_DIR = path.dirname(__file__) + "/fixtures"


def get_fixture(filepath: str):
    with open(str(FIXTURES_DIR) + "/" + filepath) as cursor:
        return cursor.read()


def get_first_node(source_code: str):
    source_tree = ast.parse(source_code)
    return source_tree.body[0]


def create_module(node: ast.AST):
    return ast.Module(body=[node])
