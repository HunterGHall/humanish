from pathlib import Path

_SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", 0, "png"),
    (b"\xFF\xD8\xFF", 0, "jpeg"),
    (b"BM", 0, "bmp"),
    (b"ID3", 0, "mp3"),
    (b"PK\x03\x04", 0, "zip"),
    (b"PK\x05\x06", 0, "zip"),
    (b"\x1F\x8B", 0, "gzip"),
    (b"%PDF-", 0, "pdf"),
    (b"MZ", 0, "pe"),
    (b"\x7fELF", 0, "elf"),
    (b"ustar", 257, "tar"),
]


def _matches_mp3_frame_sync(raw: bytes) -> bool:
    return len(raw) >= 2 and raw[0] == 0xFF and (raw[1] & 0xE0) == 0xE0


def _matches_riff(raw: bytes) -> str | None:
    if len(raw) < 12 or raw[0:4] != b"RIFF":
        return None
    form_type = raw[8:12]
    if form_type == b"WAVE":
        return "wav"
    return "riff"


def _matches_mp4(raw: bytes) -> bool:
    return len(raw) >= 12 and raw[4:8] == b"ftyp"


def _classify_pe(raw: bytes) -> str:
    DLL_CHARACTERISTIC_FLAG = 0x2000
    try:
        pe_header_offset = int.from_bytes(raw[0x3C:0x40], "little")
        coff_header = raw[pe_header_offset + 4: pe_header_offset + 24]
        characteristics = int.from_bytes(coff_header[18:20], "little")
        return "dll" if characteristics & DLL_CHARACTERISTIC_FLAG else "exe"
    except IndexError:
        return "pe"


def detect_format(path: str) -> str:
    raw = Path(path).read_bytes()

    if _matches_mp4(raw):
        return "mp4"

    riff_type = _matches_riff(raw)
    if riff_type == "wav":
        return "wav"

    for signature, offset, name in _SIGNATURES:
        if raw[offset:offset + len(signature)] == signature:
            if name == "pe":
                return _classify_pe(raw)
            return name

    if _matches_mp3_frame_sync(raw):
        return "mp3"

    return "unknown"


def detect_format_from_bytes(raw: bytes) -> str:
    if _matches_mp4(raw):
        return "mp4"

    riff_type = _matches_riff(raw)
    if riff_type == "wav":
        return "wav"

    for signature, offset, name in _SIGNATURES:
        if raw[offset:offset + len(signature)] == signature:
            if name == "pe":
                return _classify_pe(raw)
            return name

    if _matches_mp3_frame_sync(raw):
        return "mp3"

    return "unknown"


def identify_and_read(path: str) -> dict:
    from humanish.read import READERS

    fmt = detect_format(path)
    reader = READERS.get(fmt)
    if reader is None:
        return {"format": fmt, "error": "no reader available for this format"}

    result = reader(path)
    result["format"] = fmt
    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m humanish.check_format <path>")
        sys.exit(1)

    print(detect_format(sys.argv[1]))