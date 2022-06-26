from os import path


FIXTURES_DIR = path.dirname(__file__) + "/fixtures"

def get_fixture(filepath: str):
    with open(str(FIXTURES_DIR) + "/" + filepath) as cursor:
        return cursor.read()
