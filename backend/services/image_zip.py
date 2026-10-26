"""
Images from an uploaded ZIP (a manga chapter zipped on a phone). Pure functions over bytes: nothing is
extracted to disk, entry names never become paths, and every read is bounded no matter what the
archive claims about itself.
"""
import io
import re
import stat
import zipfile
from dataclasses import dataclass
from typing import List

from services.ai.index_translate import MAX_IMAGE_BYTES

MAX_IMAGES = 200
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_COMPRESSION_RATIO = 200
MAX_NAME_CHARS = 120
ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06")
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
_ENCRYPTED_FLAG = 0x1
_READ_CHUNK = 64 * 1024


class ZipRejectedError(ValueError):
    pass


class ZipTooLargeError(ZipRejectedError):
    pass


@dataclass(frozen=True)
class ExtractedImage:
    name: str
    data: bytes


def looks_like_zip(data: bytes) -> bool:
    return data.startswith(ZIP_MAGICS)


def _normalized(path: str) -> str:
    return path.replace("\\", "/")


def display_name(path: str) -> str:
    base = "".join(ch for ch in _normalized(path).rsplit("/", 1)[-1] if ch.isprintable()).strip()
    if len(base) <= MAX_NAME_CHARS:
        return base
    stem, dot, extension = base.rpartition(".")
    return stem[: MAX_NAME_CHARS - len(extension) - 1] + dot + extension


def _is_wanted(info: zipfile.ZipInfo) -> bool:
    path = _normalized(info.filename)
    if info.is_dir() or path.endswith("/"):
        return False
    segments = path.split("/")
    base = segments[-1]
    if any(segment.lower() == "__macosx" for segment in segments) or base.startswith("."):
        return False
    if not base.lower().endswith(_IMAGE_EXTENSIONS):
        return False
    mode = info.external_attr >> 16
    return stat.S_IFMT(mode) in (0, stat.S_IFREG)  # skips symlinks, devices, sockets


def _natural_key(path: str) -> List[object]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", _normalized(path).casefold())]


def _check_entry(info: zipfile.ZipInfo) -> None:
    if info.flag_bits & _ENCRYPTED_FLAG:
        raise ZipRejectedError("Encrypted ZIP files are not supported")
    if info.file_size > MAX_IMAGE_BYTES:
        raise ZipTooLargeError(f"An image in the ZIP is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB)")
    if info.file_size and (
        info.compress_size == 0 or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
    ):
        raise ZipRejectedError("ZIP entry has a suspicious compression ratio")


def _read_bounded(archive: zipfile.ZipFile, info: zipfile.ZipInfo, remaining_total: int) -> bytes:
    """Read one entry, stopping at the per-image and remaining-total caps whatever the header says."""
    limit = min(MAX_IMAGE_BYTES, remaining_total)
    data = bytearray()
    try:
        with archive.open(info) as entry:
            while piece := entry.read(_READ_CHUNK):
                data.extend(piece)
                if len(data) > limit:
                    if len(data) > MAX_IMAGE_BYTES:
                        raise ZipTooLargeError(
                            f"An image in the ZIP is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB)"
                        )
                    raise ZipTooLargeError(f"ZIP contents are too large (max {MAX_TOTAL_BYTES // (1024 * 1024)} MB)")
    except ZipRejectedError:
        raise
    except Exception:
        raise ZipRejectedError("ZIP entry could not be read") from None
    return bytes(data)


def extract_images(data: bytes) -> List[ExtractedImage]:
    """PNG/JPEG/WebP entries of a ZIP in natural path order. Raises ZipRejectedError / ZipTooLargeError."""
    if not looks_like_zip(data):
        raise ZipRejectedError("File is not a ZIP archive")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        raise ZipRejectedError("ZIP could not be read") from None

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ZipTooLargeError(f"ZIP has too many entries (max {MAX_ENTRIES})")
        wanted = sorted((info for info in infos if _is_wanted(info)), key=lambda i: _natural_key(i.filename))
        if not wanted:
            raise ZipRejectedError("ZIP contains no PNG, JPEG or WebP images")
        if len(wanted) > MAX_IMAGES:
            raise ZipTooLargeError(f"ZIP has too many images (max {MAX_IMAGES})")

        images: List[ExtractedImage] = []
        total = 0
        for info in wanted:
            _check_entry(info)
            payload = _read_bounded(archive, info, MAX_TOTAL_BYTES - total)
            total += len(payload)
            images.append(ExtractedImage(display_name(info.filename) or "image", payload))
        return images
