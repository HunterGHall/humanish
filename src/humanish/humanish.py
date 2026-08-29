from humanish.check_format import detect_format
from humanish.read import READERS


def humanish(path: str) -> dict:
    fmt = detect_format(path)
    reader = READERS.get(fmt)
    if reader is None:
        return {"format": fmt, "error": "no reader available for this format"}

    result = reader(path)
    result["format"] = fmt
    return result


def main() -> None:
    import json
    import sys

    if len(sys.argv) != 2:
        print("Usage: humanish <path>", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(humanish(sys.argv[1]), indent=2, default=str))


if __name__ == "__main__":
    main()
