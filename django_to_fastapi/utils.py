import ast
from re import sub

from black import format_str, FileMode


def unparse(node: ast.AST):
    return format_str(ast.unparse(node), mode=FileMode())


def to_snake_case(string: str):
    return "_".join(
        sub(
            "([A-Z][a-z]+)", r" \1", sub("([A-Z]+)", r" \1", string.replace("-", " "))
        ).split()
    ).lower()


def class_name_to_function(class_name: str):
    return to_snake_case(class_name.replace("View", ""))
