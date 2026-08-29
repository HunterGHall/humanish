from humanish.check_format import (
    detect_format,
    detect_format_from_bytes,
)
from humanish.humanish import humanish
from humanish.read import READERS

__version__ = "0.1.0"

__all__ = [
    "humanish",
    "detect_format",
    "detect_format_from_bytes",
    "READERS",
    "__version__",
]
