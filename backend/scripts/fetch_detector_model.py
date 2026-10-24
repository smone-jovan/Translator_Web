"""
Download a manga text-detector model (ogkalu/comic-text-and-bubble-detector, Apache-2.0) into backend/models/.

Run it yourself, once:  py -m scripts.fetch_detector_model --model detector-v4-s_int8.onnx
The server never downloads anything at runtime. The file is only kept when its SHA-256 matches the pinned value.
"""
import argparse
import hashlib
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_BASE_URL = "https://huggingface.co/ogkalu/comic-text-and-bubble-detector/resolve/main/"
DEFAULT_DEST = Path(__file__).resolve().parent.parent / "models"
DEFAULT_MODEL = "detector-v4-s_int8.onnx"
FETCH_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ModelSpec:
    url: str
    sha256: str


MODELS = {
    "detector-v4-s_int8.onnx": ModelSpec(
        _BASE_URL + "detector-v4-s_int8.onnx",
        "5fe9e4f576e49d4e7e8b0e029d6d3cdc252abd4694113e1cae120e62c931ea79",
    ),
    "detector_int8.onnx": ModelSpec(
        _BASE_URL + "detector_int8.onnx",
        "b5022ad46416b6fe4f88b0cc082cfd2ff5b1cfc624088c2f19879485493f5913",
    ),
}


class ModelChecksumError(RuntimeError):
    pass


def _http_fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("Only https:// downloads are allowed")
    with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310 (https enforced above)
        return response.read()


def download_model(
    name: str,
    dest_dir: Path,
    *,
    fetch: Callable[[str], bytes] = _http_fetch,
    expected_sha256: Optional[str] = None,
) -> Path:
    if name not in MODELS and expected_sha256 is None:
        raise KeyError(f"Unknown model: {name}")
    if Path(name).name != name:
        raise ValueError("Model name must be a plain file name")
    spec = MODELS.get(name)
    url = spec.url if spec else _BASE_URL + name
    expected = expected_sha256 or spec.sha256

    data = fetch(url)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ModelChecksumError(f"SHA-256 mismatch for {name}; file was not saved")

    dest_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest_dir, delete=False, suffix=".part") as handle:
        handle.write(data)
    target = dest_dir / name
    Path(handle.name).replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODELS), default=DEFAULT_MODEL)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()
    print(f"Saved {download_model(args.model, args.dest)}")


if __name__ == "__main__":
    main()
