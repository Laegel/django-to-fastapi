import ast
from enum import Enum
from dataclasses import dataclass
from typing import List, TypedDict


Options = TypedDict(
    "Options", {"candidate": ast.AST, "target": ast.AST, "position": int}, total=False
)


class ASTOperationAction(str, Enum):
    Replace = "replace"
    Remove = "remove"
    Insert = "insert"
    InsertBefore = "insert_before"
    InsertLast = "insert_last"
    InsertAfter = "insert_after"


@dataclass
class ASTOperation:
    action: ASTOperationAction
    options: Options


ASTOperations = List[ASTOperation]


def find_field(root: ast.AST, target: ast.AST):

    for field, child in ast.iter_fields(root):
        if isinstance(child, ast.AST):
            if child is target:
                return field
        elif isinstance(child, list):
            for childchild in child:
                if childchild is target:
                    return field


class Runner:
    @classmethod
    def execute(cls, root: ast.AST, operations: List[ASTOperation]):
        for operation in operations:
            getattr(cls, operation.action)(root, **operation.options)
        ast.fix_missing_locations(root)

    @staticmethod
    def replace(root: ast.AST, target: ast.AST, candidate: ast.AST):
        field = find_field(root, target)
        item = getattr(root, field)
        if isinstance(item, ast.AST):
            setattr(root, field, candidate)
        elif isinstance(item, list):
            item[item.index(target)] = candidate

    @staticmethod
    def remove(root: ast.AST, target: ast.AST):
        field = find_field(root, target)
        item = getattr(root, field)
        if isinstance(item, ast.AST):
            setattr(root, field, None)
        elif isinstance(item, list):
            item.remove(target)

    # Following methods are for nodes with siblings (list of nodes)
    @staticmethod
    def insert(root: List[ast.AST], target: ast.AST, position: int):
        # root: ast.AST | List[ast.AST]
        root.insert(position, target)

    @classmethod
    def insert_before(cls, root: ast.AST, target: ast.AST, candidate: ast.AST):
        field = find_field(root, target)
        cls.insert(getattr(root, field), candidate, getattr(root, field).index(target))

    @classmethod
    def insert_after(cls, root: ast.AST, target: ast.AST, candidate: ast.AST):
        field = find_field(root, target)
        cls.insert(
            getattr(root, field), candidate, getattr(root, field).index(target) + 1
        )

    @classmethod
    def insert_last(cls, root: ast.AST, target: ast.AST):
        field = "body"
        getattr(root, field).append(target)


# class ASTOperationVisitor(ast.NodeVisitor):
#     def __init__(self):
#         self.operations: ASTOperations = []

#     def execute():
#         return node
