from pathlib import Path


SOURCE_FILE = "bot_broken.py"
OUTPUT_FILE = "bot_fixed.py"


def repair_python_strings(source: str) -> str:
    """
    Repairs literal newlines inside ordinary Python strings.

    Example:
        "hello
        world"

    Becomes:
        "hello\nworld"

    Triple-quoted strings are left unchanged.
    """

    result = []
    i = 0
    length = len(source)

    quote_char = None
    triple_quoted = False
    escaped = False

    while i < length:
        char = source[i]

        # Outside a string
        if quote_char is None:
            if source.startswith('"""', i):
                result.append('"""')
                quote_char = '"'
                triple_quoted = True
                i += 3
                continue

            if source.startswith("'''", i):
                result.append("'''")
                quote_char = "'"
                triple_quoted = True
                i += 3
                continue

            if char in ('"', "'"):
                result.append(char)
                quote_char = char
                triple_quoted = False
                escaped = False
                i += 1
                continue

            result.append(char)
            i += 1
            continue

        # Inside a triple-quoted string
        if triple_quoted:
            closing = quote_char * 3

            if source.startswith(closing, i):
                result.append(closing)
                i += 3
                quote_char = None
                triple_quoted = False
                continue

            result.append(char)
            i += 1
            continue

        # Inside a normal quoted string
        if escaped:
            result.append(char)
            escaped = False
            i += 1
            continue

        if char == "\\":
            result.append(char)
            escaped = True
            i += 1
            continue

        if char == quote_char:
            result.append(char)
            quote_char = None
            i += 1
            continue

        if char == "\n":
            result.append(r"\n")
            i += 1
            continue

        result.append(char)
        i += 1

    if quote_char is not None and not triple_quoted:
        raise SyntaxError("An ordinary quoted string is still unterminated.")

    return "".join(result)


def main() -> None:
    source_path = Path(SOURCE_FILE)
    output_path = Path(OUTPUT_FILE)

    if not source_path.exists():
        raise FileNotFoundError(f"Missing source file: {SOURCE_FILE}")

    source = source_path.read_text(encoding="utf-8")
    repaired = repair_python_strings(source)
    output_path.write_text(repaired, encoding="utf-8")

    print(f"Created repaired file: {OUTPUT_FILE}")
    print("Run the following command to check syntax:")
    print(f"python -m py_compile {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
