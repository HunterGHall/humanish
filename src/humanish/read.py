import gzip
import re
import tarfile
import wave
import zipfile
from pathlib import Path


def read_png(path: str) -> dict:
    color_type_names = {
        0: "grayscale",
        2: "rgb",
        3: "palette",
        4: "grayscale+alpha",
        6: "rgba",
    }

    raw = Path(path).read_bytes()

    image_info = None
    chunk_list = []

    position = 8
    while position + 8 <= len(raw):
        chunk_length = int.from_bytes(raw[position:position + 4], "big")
        chunk_type = raw[position + 4:position + 8].decode("ascii", errors="replace")
        chunk_data = raw[position + 8: position + 8 + chunk_length]

        chunk_list.append({
            "type": chunk_type,
            "length": chunk_length,
            "offset": position,
        })

        if chunk_type == "IHDR":
            image_info = {
                "width": int.from_bytes(chunk_data[0:4], "big"),
                "height": int.from_bytes(chunk_data[4:8], "big"),
                "bit_depth": chunk_data[8],
                "color_type": color_type_names.get(chunk_data[9], chunk_data[9]),
                "interlaced": bool(chunk_data[12]),
            }

        position += 4 + 4 + chunk_length + 4

        if chunk_type == "IEND":
            break

    return {
        "image_info": image_info,
        "chunks": chunk_list,
    }


def read_jpeg(path: str) -> dict:
    raw = Path(path).read_bytes()
    if raw[:2] != b"\xFF\xD8":
        return {"error": "not a JPEG file"}

    width = height = components = None
    markers = []

    position = 2
    while position < len(raw) - 1:
        if raw[position] != 0xFF:
            position += 1
            continue

        marker = raw[position + 1]

        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            position += 2
            continue

        if position + 4 > len(raw):
            break

        segment_length = int.from_bytes(raw[position + 2:position + 4], "big")
        markers.append({"marker": f"0x{marker:02X}", "offset": position, "length": segment_length})

        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            height = int.from_bytes(raw[position + 5:position + 7], "big")
            width = int.from_bytes(raw[position + 7:position + 9], "big")
            components = raw[position + 9]

        if marker == 0xDA:
            break

        position += 2 + segment_length

    return {
        "width": width,
        "height": height,
        "components": components,
        "markers": markers,
        "byte_size": len(raw),
    }


def read_bmp(path: str) -> dict:
    raw = Path(path).read_bytes()
    if raw[:2] != b"BM":
        return {"error": "not a BMP file"}

    file_size = int.from_bytes(raw[2:6], "little")
    pixel_data_offset = int.from_bytes(raw[10:14], "little")
    width = int.from_bytes(raw[18:22], "little", signed=True)
    height = int.from_bytes(raw[22:26], "little", signed=True)
    bits_per_pixel = int.from_bytes(raw[28:30], "little")
    compression = int.from_bytes(raw[30:34], "little")

    return {
        "width": width,
        "height": abs(height),
        "top_down": height < 0,
        "bits_per_pixel": bits_per_pixel,
        "compression": compression,
        "pixel_data_offset": pixel_data_offset,
        "byte_size": file_size,
    }


def read_wav(path: str) -> dict:
    with wave.open(path, "rb") as audio:
        frame_count = audio.getnframes()
        sample_rate = audio.getframerate()
        duration = frame_count / sample_rate if sample_rate else 0.0

        return {
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "sample_rate_hz": sample_rate,
            "frame_count": frame_count,
            "duration_seconds": round(duration, 3),
            "compression_type": audio.getcomptype(),
        }


def read_mp3(path: str) -> dict:
    mpeg_version_names = {0b00: "MPEG 2.5", 0b10: "MPEG 2", 0b11: "MPEG 1"}
    layer_names = {0b01: "Layer III", 0b10: "Layer II", 0b11: "Layer I"}
    channel_mode_names = {0b00: "stereo", 0b01: "joint_stereo", 0b10: "dual_channel", 0b11: "mono"}
    bitrate_table_v1_l3 = [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None]
    sample_rate_table_v1 = [44100, 48000, 32000, None]

    raw = Path(path).read_bytes()

    id3_version = None
    id3_size = 0
    if raw[:3] == b"ID3":
        id3_version = f"2.{raw[3]}.{raw[4]}"
        size_bytes = raw[6:10]
        id3_size = (
            ((size_bytes[0] & 0x7F) << 21)
            | ((size_bytes[1] & 0x7F) << 14)
            | ((size_bytes[2] & 0x7F) << 7)
            | (size_bytes[3] & 0x7F)
        ) + 10

    frame_info = None
    position = id3_size
    while position < len(raw) - 4:
        if raw[position] == 0xFF and (raw[position + 1] & 0xE0) == 0xE0:
            b1, b2, b3, b4 = raw[position:position + 4]
            version_bits = (b2 >> 3) & 0b11
            layer_bits = (b2 >> 1) & 0b11
            bitrate_index = (b3 >> 4) & 0b1111
            sample_rate_index = (b3 >> 2) & 0b11
            channel_mode_bits = (b4 >> 6) & 0b11

            bitrate_kbps = None
            if version_bits == 0b11 and layer_bits == 0b01 and 0 < bitrate_index < 15:
                bitrate_kbps = bitrate_table_v1_l3[bitrate_index]

            sample_rate_hz = None
            if version_bits == 0b11 and sample_rate_index < 3:
                sample_rate_hz = sample_rate_table_v1[sample_rate_index]

            frame_info = {
                "mpeg_version": mpeg_version_names.get(version_bits, "unknown"),
                "layer": layer_names.get(layer_bits, "unknown"),
                "bitrate_kbps": bitrate_kbps,
                "sample_rate_hz": sample_rate_hz,
                "channel_mode": channel_mode_names.get(channel_mode_bits, "unknown"),
                "offset": position,
            }
            break

        position += 1

    return {
        "id3_version": id3_version,
        "id3_tag_size": id3_size,
        "first_frame": frame_info,
        "byte_size": len(raw),
    }


def read_zip(path: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        first_corrupt_file = archive.testzip()

        entries = []
        for info in archive.infolist():
            entries.append({
                "name": info.filename,
                "is_folder": info.is_dir(),
                "uncompressed_size": info.file_size,
                "compressed_size": info.compress_size,
                "last_modified": "%04d-%02d-%02d %02d:%02d:%02d" % info.date_time,
                "checksum_crc32": format(info.CRC, "08x"),
            })

    return {
        "first_corrupt_file": first_corrupt_file,
        "entries": entries,
    }


def read_tar(path: str) -> dict:
    with tarfile.open(path) as archive:
        entries = []
        for member in archive.getmembers():
            entries.append({
                "name": member.name,
                "is_folder": member.isdir(),
                "size": member.size,
                "mode": oct(member.mode),
                "modified_unix": member.mtime,
            })

    return {
        "entries": entries,
    }


def read_gzip(path: str) -> dict:
    FLAG_EXTRA_FIELD = 0b00000100
    FLAG_HAS_FILENAME = 0b00001000
    FLAG_HAS_COMMENT = 0b00010000

    raw = Path(path).read_bytes()
    flags = raw[3]
    position = 10

    if flags & FLAG_EXTRA_FIELD:
        extra_length = int.from_bytes(raw[position:position + 2], "little")
        position += 2 + extra_length

    original_name = None
    if flags & FLAG_HAS_FILENAME:
        end = raw.index(b"\x00", position)
        original_name = raw[position:end].decode("latin-1")
        position = end + 1

    comment = None
    if flags & FLAG_HAS_COMMENT:
        end = raw.index(b"\x00", position)
        comment = raw[position:end].decode("latin-1")
        position = end + 1

    return {
        "modified_time_unix": int.from_bytes(raw[4:8], "little"),
        "original_filename": original_name,
        "comment": comment,
        "decompressed_size_bytes": len(gzip.decompress(raw)),
    }


def read_pdf(path: str) -> dict:
    raw = Path(path).read_bytes()

    version_match = re.match(rb"%PDF-(\d+\.\d+)", raw)
    declared_size_match = re.search(rb"/Size\s+(\d+)", raw)

    object_ids_found = set(re.findall(rb"(\d+)\s+(\d+)\s+obj\b", raw))
    page_count = len(re.findall(rb"/Type\s*/Page\b", raw))

    return {
        "pdf_version": version_match.group(1).decode() if version_match else None,
        "declared_object_count": int(declared_size_match.group(1)) if declared_size_match else None,
        "objects_actually_found": len(object_ids_found),
        "page_count": page_count,
        "is_encrypted": b"/Encrypt" in raw,
        "ends_with_eof_marker": raw.rstrip().endswith(b"%%EOF"),
        "byte_size": len(raw),
    }


def read_pe(path: str) -> dict:
    DLL_CHARACTERISTIC_FLAG = 0x2000

    machine_type_names = {
        0x014C: "x86 (32-bit)",
        0x8664: "x86-64 (64-bit)",
        0xAA64: "ARM64",
    }
    subsystem_names = {
        2: "windows_gui",
        3: "windows_console",
    }

    raw = Path(path).read_bytes()

    pe_header_offset = int.from_bytes(raw[0x3C:0x40], "little")

    coff_header = raw[pe_header_offset + 4: pe_header_offset + 24]
    machine = int.from_bytes(coff_header[0:2], "little")
    section_count = int.from_bytes(coff_header[2:4], "little")
    timestamp = int.from_bytes(coff_header[4:8], "little")
    characteristics = int.from_bytes(coff_header[18:20], "little")
    optional_header_size = int.from_bytes(coff_header[16:18], "little")

    optional_header = raw[pe_header_offset + 24: pe_header_offset + 24 + optional_header_size]
    subsystem = None
    if optional_header_size >= 70:
        subsystem = int.from_bytes(optional_header[68:70], "little")

    is_dll = bool(characteristics & DLL_CHARACTERISTIC_FLAG)

    return {
        "architecture": machine_type_names.get(machine, f"unknown (0x{machine:04x})"),
        "file_kind": "dll" if is_dll else "exe",
        "section_count": section_count,
        "build_timestamp_unix": timestamp,
        "subsystem": subsystem_names.get(subsystem, subsystem),
        "byte_size": len(raw),
    }


def read_elf(path: str) -> dict:
    type_names = {1: "relocatable", 2: "executable", 3: "shared_object", 4: "core"}
    machine_names = {0x03: "x86", 0x3E: "x86-64", 0x28: "ARM", 0xB7: "ARM64"}

    raw = Path(path).read_bytes()
    if raw[:4] != b"\x7fELF":
        return {"error": "not an ELF file"}

    is_64bit = raw[4] == 2
    endianness = "little" if raw[5] == 1 else "big"
    e_type = int.from_bytes(raw[16:18], endianness)
    e_machine = int.from_bytes(raw[18:20], endianness)

    return {
        "class": "ELF64" if is_64bit else "ELF32",
        "endianness": endianness,
        "type": type_names.get(e_type, f"unknown ({e_type})"),
        "machine": machine_names.get(e_machine, f"unknown (0x{e_machine:02x})"),
        "byte_size": len(raw),
    }


def _walk_mp4_boxes(data: bytes, start: int, end: int):
    position = start
    while position + 8 <= end:
        box_size = int.from_bytes(data[position:position + 4], "big")
        box_type = data[position + 4:position + 8].decode("latin-1")
        content_start = position + 8

        if box_size == 1:
            box_size = int.from_bytes(data[position + 8:position + 16], "big")
            content_start = position + 16
        elif box_size == 0:
            box_size = end - position

        box_end = position + box_size
        if box_end <= content_start or box_end > end:
            break

        yield box_type, position, content_start, box_end
        position = box_end


def _read_movie_header(data: bytes, content_start: int) -> dict | None:
    version = data[content_start]

    if version == 1:
        timescale = int.from_bytes(data[content_start + 20:content_start + 24], "big")
        duration_units = int.from_bytes(data[content_start + 24:content_start + 32], "big")
    else:
        timescale = int.from_bytes(data[content_start + 12:content_start + 16], "big")
        duration_units = int.from_bytes(data[content_start + 16:content_start + 20], "big")

    if not timescale:
        return None

    return {
        "timescale": timescale,
        "duration_units": duration_units,
        "duration_seconds": round(duration_units / timescale, 3),
    }


def read_mp4(path: str) -> dict:
    raw = Path(path).read_bytes()

    major_brand = None
    compatible_brands = []
    movie_info = None
    box_list = []

    for box_type, box_start, content_start, box_end in _walk_mp4_boxes(raw, 0, len(raw)):
        box_list.append({
            "type": box_type,
            "offset": box_start,
            "size": box_end - box_start,
        })

        if box_type == "ftyp":
            major_brand = raw[content_start:content_start + 4].decode("latin-1").strip()
            compatible_brands = [
                raw[i:i + 4].decode("latin-1").strip()
                for i in range(content_start + 8, box_end, 4)
            ]

        elif box_type == "moov":
            for inner_type, _s, inner_content_start, _e in _walk_mp4_boxes(raw, content_start, box_end):
                if inner_type == "mvhd":
                    movie_info = _read_movie_header(raw, inner_content_start)
                    break

    return {
        "major_brand": major_brand,
        "compatible_brands": compatible_brands,
        "box_count": len(box_list),
        "boxes": box_list,
        "movie_info": movie_info,
        "byte_size": len(raw),
    }


READERS = {
    "png": read_png,
    "jpeg": read_jpeg,
    "jpg": read_jpeg,
    "bmp": read_bmp,
    "wav": read_wav,
    "mp3": read_mp3,
    "zip": read_zip,
    "tar": read_tar,
    "gzip": read_gzip,
    "pdf": read_pdf,
    "exe": read_pe,
    "dll": read_pe,
    "elf": read_elf,
    "mp4": read_mp4,
}


if __name__ == "__main__":
    print(read_mp3('file.mp3'))