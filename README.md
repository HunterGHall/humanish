# humanish

Detect a file's real format from its magic bytes (not its extension) and get a
human-readable summary of what's inside it.

Supports PNG, JPEG, BMP, WAV, MP3, ZIP, TAR, GZIP, PDF, PE (EXE/DLL), ELF, and
MP4. Pure standard library, no dependencies.

## Install

```bash
pip install humanish
```

## Usage

```python
from humanish import humanish, detect_format

detect_format("mystery.bin")          # -> "png"

humanish("photo.jpg")
# {
#   "format": "jpeg",
#   "width": 1920,
#   "height": 1080,
#   "components": 3,
#   ...
# }
```

Detect from bytes you already have in memory:

```python
from humanish import detect_format_from_bytes

detect_format_from_bytes(open("mystery.bin", "rb").read(64))
```

## Command line

```bash
humanish path/to/file
```

Prints the format and content summary as JSON.

## License

MIT
