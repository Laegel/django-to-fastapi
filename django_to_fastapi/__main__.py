from hashlib import md5
import os
from django_to_fastapi.modules import process_code
from django_to_fastapi.routes import get_modules_from_routes, get_routes
from django_to_fastapi.utils import unparse


def _read_file(path: str):
    with open(path) as cursor:
        return cursor.read()


def main(urls_path: str):
    urls_source_code = _read_file(urls_path)

    routes = get_routes(urls_source_code)

    modules = get_modules_from_routes(urls_source_code, routes)

    root_path = os.sep.join(urls_path.split(os.sep)[0:-2])

    for module in modules:
        source_code = _read_file(root_path + "/" + module + ".py")
        migrated = process_code(source_code, routes)
        with open("./output/" + (module.replace("/", "-") + ".py"), "w") as cursor:
            cursor.write(unparse(migrated))


main("/home/laegel/Workspace/impala/impalapimono/impalapi/urls.py")
