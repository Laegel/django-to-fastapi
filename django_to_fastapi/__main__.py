import os
import shutil
from sys import argv

from django_to_fastapi.modules import (
    generate_bootstrap_module,
    generate_entrypoint,
    process_code,
)
from django_to_fastapi.routes import get_modules_from_routes, get_routes
from django_to_fastapi.utils import Logger, unparse


def _read_file(path: str):
    with open(path) as cursor:
        return cursor.read()


def main(urls_path: str, destination_path: str):
    urls_source_code = _read_file(urls_path)

    routes = get_routes(urls_source_code)

    modules = get_modules_from_routes(urls_source_code, routes)

    root_path = os.sep.join(urls_path.split(os.sep)[0:-2])

    for module in modules:
        Logger.current_module = module
        source_code = _read_file(root_path + "/" + module + ".py")
        # fix_missing_annotations(source_code)
        migrated = process_code(source_code, routes)
        os.makedirs(os.path.dirname(destination_path + "/" + module), exist_ok=True)
        with open(
            destination_path + "/" + module + ".py", "w"
        ) as cursor:
            cursor.write(unparse(migrated))

    with open(destination_path + "/bootstrap.py", "w") as cursor:
        cursor.write(generate_bootstrap_module())

    with open(destination_path + "/main.py", "w") as cursor:
        cursor.write(generate_entrypoint())

    with open(destination_path + "/main.py", "w") as cursor:
        cursor.write(generate_entrypoint())

    os.makedirs(destination_path + "/conf", exist_ok=True)
    shutil.copyfile(os.sep.join(urls_path.split(os.sep)[0:-1]) + "/settings.py", destination_path + "/conf/settings.py")
    print(f"Finished with {Logger.warns_counter} warnings.")


try:
    destination_path = argv[2]
except IndexError:
    destination_path = "./output"
try:
    main(urls_path=argv[1], destination_path=destination_path)
except IndexError:
    print("Path to urls.py should be provided as a position argument")
