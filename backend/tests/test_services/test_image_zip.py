import io
import os
import zipfile

import pytest

from services import image_zip
from services.image_zip import ZipRejectedError, ZipTooLargeError, extract_images

PNG = b"\x89PNG\r\n\x1a\nfake-png"
JPG = b"\xff\xd8\xff\xe0fake-jpg"


def make_zip(entries, compression=zipfile.ZIP_DEFLATED):
    """entries: list of (name, bytes) or (ZipInfo, bytes)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buffer.getvalue()


def names(images):
    return [image.name for image in images]


class TestExtractImages:
    def test_returns_images_in_natural_order(self):
        data = make_zip([("p10.png", PNG), ("p2.jpg", JPG), ("p1.jpeg", JPG)])

        images = extract_images(data)

        assert names(images) == ["p1.jpeg", "p2.jpg", "p10.png"]
        assert images[1].data == JPG

    def test_sorts_by_full_path_then_number(self):
        data = make_zip([("ch2/p1.png", PNG), ("ch10/p1.png", PNG), ("ch1/p2.png", PNG), ("ch1/p10.png", PNG)])

        assert names(extract_images(data)) == ["p2.png", "p10.png", "p1.png", "p1.png"]  # ch1, ch1, ch2, ch10

    def test_skips_directories_metadata_dotfiles_and_non_images(self):
        data = make_zip(
            [
                ("folder/", b""),
                ("__MACOSX/._a.png", PNG),
                (".hidden.png", PNG),
                ("Thumbs.db", b"x"),
                ("notes.txt", b"hi"),
                ("inner.zip", make_zip([("deep.png", PNG)])),
                ("a.PNG", PNG),
            ]
        )

        assert names(extract_images(data)) == ["a.PNG"]

    def test_symlink_entries_are_skipped(self):
        link = zipfile.ZipInfo("link.png")
        link.external_attr = (0o120777) << 16
        data = make_zip([(link, b"/etc/passwd"), ("real.png", PNG)])

        assert names(extract_images(data)) == ["real.png"]

    @pytest.mark.parametrize(
        "entry,expected",
        [
            ("../../evil.png", "evil.png"),
            ("/abs/path/a.png", "a.png"),
            ("C:\\x\\y\\b.jpg", "b.jpg"),
            ("sub/dir/c.png", "c.png"),
        ],
    )
    def test_names_are_reduced_to_a_safe_basename(self, entry, expected, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        images = extract_images(make_zip([(entry, PNG)]))

        assert names(images) == [expected]
        assert list(tmp_path.iterdir()) == []  # nothing was written to disk

    def test_control_characters_are_stripped_and_length_is_capped(self):
        long_name = "x" * 300 + ".png"
        images = extract_images(make_zip([("bad\x00\x1bname.png", PNG), (long_name, PNG)]))

        assert all(len(n) <= 120 and n.isprintable() for n in names(images))

    def test_rejects_non_zip_and_corrupt_data(self):
        with pytest.raises(ZipRejectedError):
            extract_images(b"<html>not a zip</html>")
        with pytest.raises(ZipRejectedError):
            extract_images(b"PK\x03\x04 garbage garbage garbage")

    def test_rejects_encrypted_entries(self):
        data = bytearray(make_zip([("a.png", PNG)]))
        # set the "encrypted" general-purpose flag in both the local and central headers
        for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            data[data.index(signature) + offset] |= 0x01

        with pytest.raises(ZipRejectedError):
            extract_images(bytes(data))

    def test_zip_without_images_is_rejected(self):
        with pytest.raises(ZipRejectedError):
            extract_images(make_zip([("readme.txt", b"hello")]))
        with pytest.raises(ZipRejectedError):
            extract_images(make_zip([]))


class TestLimits:
    def test_too_many_images_is_rejected_before_reading_them(self, monkeypatch):
        monkeypatch.setattr(image_zip, "MAX_IMAGES", 3)
        data = make_zip([(f"{i}.png", PNG) for i in range(4)])

        with pytest.raises(ZipTooLargeError):
            extract_images(data)

    def test_entry_over_the_per_image_cap_is_rejected(self, monkeypatch):
        monkeypatch.setattr(image_zip, "MAX_IMAGE_BYTES", 1024)
        data = make_zip([("big.png", os.urandom(4096))], compression=zipfile.ZIP_STORED)

        with pytest.raises(ZipTooLargeError):
            extract_images(data)

    def test_extreme_compression_ratio_is_rejected_as_a_zip_bomb(self):
        data = make_zip([("bomb.png", b"\x00" * (5 * 1024 * 1024))])  # under the size cap, ~5 KB compressed

        with pytest.raises(ZipRejectedError) as error:
            extract_images(data)

        assert not isinstance(error.value, ZipTooLargeError)  # rejected by the ratio check, not the size cap

    def test_total_extracted_size_is_capped(self, monkeypatch):
        monkeypatch.setattr(image_zip, "MAX_TOTAL_BYTES", 1500)
        data = make_zip([(f"{i}.png", os.urandom(600)) for i in range(4)], compression=zipfile.ZIP_STORED)

        with pytest.raises(ZipTooLargeError):
            extract_images(data)

    def test_declared_size_is_not_trusted(self, monkeypatch):
        """The central directory claims 10 bytes but the entry really holds more: reading is bounded anyway."""
        monkeypatch.setattr(image_zip, "MAX_IMAGE_BYTES", 2048)
        payload = os.urandom(8192)
        data = bytearray(make_zip([("liar.png", payload)], compression=zipfile.ZIP_STORED))
        central = data.index(b"PK\x01\x02")
        data[central + 24 : central + 28] = (10).to_bytes(4, "little")  # uncompressed size in central dir

        with pytest.raises((ZipTooLargeError, ZipRejectedError)):
            extract_images(bytes(data))

    def test_too_many_entries_are_rejected(self, monkeypatch):
        monkeypatch.setattr(image_zip, "MAX_ENTRIES", 5)
        data = make_zip([(f"d{i}/", b"") for i in range(6)] + [("a.png", PNG)])

        with pytest.raises(ZipTooLargeError):
            extract_images(data)
