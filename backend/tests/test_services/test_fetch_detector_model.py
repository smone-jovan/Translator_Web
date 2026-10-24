import hashlib

import pytest

from scripts.fetch_detector_model import MODELS, ModelChecksumError, download_model


def _fake_fetch(payload: bytes):
    return lambda url: payload


def test_known_models_have_pinned_sha256_and_https_urls():
    assert set(MODELS) == {"detector-v4-s_int8.onnx", "detector_int8.onnx"}
    for spec in MODELS.values():
        assert spec.url.startswith("https://huggingface.co/")
        assert len(spec.sha256) == 64


def test_download_writes_file_when_checksum_matches(tmp_path):
    payload = b"onnx-bytes"
    target = download_model("m.onnx", tmp_path, fetch=_fake_fetch(payload), expected_sha256=hashlib.sha256(payload).hexdigest())

    assert target.read_bytes() == payload


def test_download_refuses_and_leaves_no_file_on_checksum_mismatch(tmp_path):
    with pytest.raises(ModelChecksumError):
        download_model("m.onnx", tmp_path, fetch=_fake_fetch(b"tampered"), expected_sha256="0" * 64)

    assert list(tmp_path.iterdir()) == []


def test_unknown_model_name_is_rejected(tmp_path):
    with pytest.raises(KeyError):
        download_model("../../evil.onnx", tmp_path, fetch=_fake_fetch(b""))
