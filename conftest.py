from sybil import Sybil
from sybil.parsers.codeblock import PythonCodeBlockParser
from sybil.parsers.doctest import DocTestParser

from dotenv import load_dotenv

load_dotenv()

pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(),
        PythonCodeBlockParser(future_imports=["print_function"]),
    ],
    pattern="*.md",
    fixtures=[],
).pytest()
