import ast
import logging
from re import sub
from typing import Callable, List, TypeVar

from black import format_str, FileMode
from option import NONE, Option, Some

# from pytype import analyze, load_pytd, config
# from pytype.pytd import visitors
from termcolor import colored


logging.basicConfig(
    level=logging.INFO,
)

_logger = logging.getLogger("codemod")
_logger.addHandler(logging.StreamHandler())


class Logger:

    current_module = ""
    warns_counter = 0

    @classmethod
    def format(cls, message: str, sample_code="", color="white", line=-1):
        return (
            colored(message, color, attrs=["bold"])
            + " in "
            + cls.current_module
            + (f" on line {line}" if line else "")
            + (f"\n```\n{sample_code}```" if sample_code else "")
        )

    @classmethod
    def print_info(cls, message: str, sample_code="", line=-1):
        _logger.info(cls.format(message, sample_code=sample_code, line=line))

    @classmethod
    def print_warn(cls, message: str, sample_code="", line=-1):
        _logger.warning(
            cls.format(message, sample_code=sample_code, color="yellow", line=line)
        )
        cls.warns_counter += 1


def unparse(node: ast.AST):
    return format_string(ast.unparse(node))


def format_string(source_code: str):
    return format_str(source_code, mode=FileMode())


def to_snake_case(string: str):
    return "_".join(
        sub(
            "([A-Z][a-z]+)", r" \1", sub("([A-Z]+)", r" \1", string.replace("-", " "))
        ).split()
    ).lower()


def to_camel_case(string: str):
    string = sub(r"(_|-)+", " ", string).title().replace(" ", "")
    return "".join([string[0].lower(), string[1:]])


def to_pascal_case(string: str):
    return string[0:1].capitalize() + to_camel_case(string)[1:]


def class_name_to_function(class_name: str):
    return to_snake_case(class_name.replace("View", ""))


# def fix_missing_annotations(src):
#     options = config.Options.create(
#         # module_name=module_name,
#         quick=True,
#         # use_pickled_files=True, analyze_annotated=analyze_annotated,
#         # **self._GetPythonpathArgs(pythonpath, imports_map)
#     )
#     loader = load_pytd.create_loader(options)
#     ret = analyze.infer_types(src, options=options, loader=loader)
#     errorlog = ret.errorlog
#     unit = ret.ast
#     unit.Visit(visitors.VerifyVisitor())
#     if errorlog:
#         errorlog.print_to_stderr()

#     unit


T = TypeVar("T")


def find(items: List[T], predicate: Callable[[T], bool]):
    try:
        return Some(next(item for item in items if predicate(item)))
    except StopIteration:
        return NONE


def get_at(items: List[T], position: int) -> Option[T] | Option[None]:
    try:
        return Some(items[position])
    except IndexError:
        return NONE


def get_arg_or_keyword(node: ast.Call, arg: str, position: int):
    return find(node.keywords, lambda keyword: keyword.arg == arg) or get_at(
        node.args, position
    )
