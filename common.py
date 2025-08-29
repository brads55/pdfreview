import re
from typing import Any


def process_template(filename: str, substitutions: list[list[str]], config: dict[str, Any]):
    """Prints out the file specified to the standard output, performing any requested substitutions.
    The substitutions are in the form [[r'regex', 'replacement'], ...]"""
    substitutions.append([r"%BRANDING%", config["branding"]])
    output = ""
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            for substitution in substitutions:
                line = re.sub(substitution[0], substitution[1], line)
            output += line
    return output
