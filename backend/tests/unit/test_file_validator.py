"""Phase 1.3.4 — File validation unit tests."""

import pytest

from app.core.config import settings
from app.exceptions.base import (
    FileTooLargeException,
    InvalidFilenameException,
    InvalidFileTypeException,
)
from app.schemas.complaint_image import ImageType
from app.utils.file_validation import (
    ALLOWED_MIME_TYPES,
    DEFAULT_MAX_FILE_SIZES_MB,
    FileValidator,
    is_unsafe_filename,
    read_bounded,
    sanitize_filename,
    validate_magic_bytes,
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16
HEIC = b"\x00\x00\x00\x20ftypheic" + b"\x00" * 16


class FakeReader:
    """Minimal async reader over fixed bytes."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""
        end = len(self._data) if size < 0 else self._pos + size
        chunk = self._data[self._pos : end]
        self._pos += len(chunk)
        return chunk


@pytest.fixture
def validator() -> FileValidator:
    return FileValidator.from_settings(settings)


class TestAllowedTypes:
    def test_evidence_allows_heic(self) -> None:
        assert "image/heic" in ALLOWED_MIME_TYPES[ImageType.EVIDENCE]

    def test_progress_does_not_allow_heic(self) -> None:
        assert "image/heic" not in ALLOWED_MIME_TYPES[ImageType.PROGRESS]

    def test_completion_does_not_allow_heic(self) -> None:
        assert "image/heic" not in ALLOWED_MIME_TYPES[ImageType.COMPLETION]

    def test_default_size_limits(self) -> None:
        assert DEFAULT_MAX_FILE_SIZES_MB[ImageType.EVIDENCE] == 10
        assert DEFAULT_MAX_FILE_SIZES_MB[ImageType.PROGRESS] == 5
        assert DEFAULT_MAX_FILE_SIZES_MB[ImageType.COMPLETION] == 5


class TestDeclaredMime:
    @pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "image/webp", "image/heic"])
    def test_evidence_accepts_allowed(self, validator: FileValidator, mime: str) -> None:
        assert validator.validate_declared_mime(mime, ImageType.EVIDENCE) == mime

    @pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "image/webp"])
    def test_progress_accepts_allowed(self, validator: FileValidator, mime: str) -> None:
        assert validator.validate_declared_mime(mime, ImageType.PROGRESS) == mime

    def test_heic_rejected_for_progress(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_declared_mime("image/heic", ImageType.PROGRESS)

    def test_heic_rejected_for_completion(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_declared_mime("image/heic", ImageType.COMPLETION)

    def test_gif_rejected(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_declared_mime("image/gif", ImageType.EVIDENCE)

    def test_text_rejected(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_declared_mime("text/plain", ImageType.EVIDENCE)

    def test_missing_mime_rejected(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_declared_mime(None, ImageType.EVIDENCE)

    def test_blank_mime_rejected(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_declared_mime("   ", ImageType.EVIDENCE)

    def test_mime_normalized_case_and_whitespace(self, validator: FileValidator) -> None:
        assert (
            validator.validate_declared_mime("  IMAGE/JPEG ", ImageType.EVIDENCE)
            == "image/jpeg"
        )

    def test_error_code_is_invalid_file_type(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException) as exc:
            validator.validate_declared_mime("image/gif", ImageType.EVIDENCE)
        assert exc.value.error_code == "INVALID_FILE_TYPE"
        assert exc.value.status_code == 400


class TestMagicBytes:
    @pytest.mark.parametrize(
        ("content", "mime"),
        [
            (JPEG, "image/jpeg"),
            (PNG, "image/png"),
            (WEBP, "image/webp"),
            (HEIC, "image/heic"),
        ],
    )
    def test_valid_signatures(self, content: bytes, mime: str) -> None:
        assert validate_magic_bytes(content, mime) is True

    def test_jpeg_bytes_but_png_declared(self) -> None:
        assert validate_magic_bytes(JPEG, "image/png") is False

    def test_random_binary_rejected(self) -> None:
        assert validate_magic_bytes(b"not an image at all", "image/jpeg") is False

    def test_empty_rejected(self) -> None:
        assert validate_magic_bytes(b"", "image/jpeg") is False

    def test_riff_without_webp_rejected(self) -> None:
        assert validate_magic_bytes(b"RIFF\x00\x00\x00\x00WAVE", "image/webp") is False

    def test_heic_wrong_brand_rejected(self) -> None:
        assert validate_magic_bytes(b"\x00\x00\x00\x20ftypmp42xxxx", "image/heic") is False

    def test_unknown_mime_rejected(self) -> None:
        assert validate_magic_bytes(JPEG, "image/tiff") is False


class TestContentValidation:
    def test_valid_jpeg(self, validator: FileValidator) -> None:
        validator.validate_content(JPEG, "image/jpeg")

    def test_valid_png(self, validator: FileValidator) -> None:
        validator.validate_content(PNG, "image/png")

    def test_valid_webp(self, validator: FileValidator) -> None:
        validator.validate_content(WEBP, "image/webp")

    def test_valid_heic(self, validator: FileValidator) -> None:
        validator.validate_content(HEIC, "image/heic")

    def test_empty_file_rejected(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_content(b"", "image/jpeg")

    def test_content_mismatch_rejected(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_content(b"just text pretending to be a jpeg", "image/jpeg")

    def test_png_content_but_jpeg_declared(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFileTypeException):
            validator.validate_content(PNG, "image/jpeg")


class TestFilenameSanitization:
    def test_plain_filename_preserved(self) -> None:
        assert sanitize_filename("photo.jpg") == "photo.jpg"

    def test_spaces_removed(self) -> None:
        assert sanitize_filename("my photo.png") == "myphoto.png"

    def test_path_separators_stripped(self) -> None:
        assert "/" not in sanitize_filename("../../evil.jpg")
        assert "\\" not in sanitize_filename("..\\..\\evil.jpg")

    def test_unicode_filename_produces_safe_name(self) -> None:
        result = sanitize_filename("фото.jpg")
        assert result
        assert all(ch.isascii() for ch in result)

    def test_empty_filename_falls_back(self) -> None:
        assert sanitize_filename("") == "image"
        assert sanitize_filename(None) == "image"

    def test_control_characters_removed(self) -> None:
        assert "\x00" not in sanitize_filename("evil\x00name.jpg")

    def test_long_filename_truncated(self) -> None:
        result = sanitize_filename("a" * 500 + ".jpg")
        assert len(result) <= 104
        assert result.endswith(".jpg")

    def test_unsafe_characters_removed(self) -> None:
        result = sanitize_filename('we<ird>:"|?*.jpg')
        assert "<" not in result and ">" not in result and "|" not in result


class TestUnsafeFilenameDetection:
    @pytest.mark.parametrize(
        "filename",
        [
            "../../secret.txt",
            "..\\..\\secret.txt",
            "/etc/passwd",
            "C:\\Windows\\system32\\file",
            "dir/file.jpg",
            "..",
            ".",
            "",
            None,
            "bad\x00name.jpg",
            "bad\nname.jpg",
        ],
    )
    def test_dangerous_names_detected(self, filename: str | None) -> None:
        assert is_unsafe_filename(filename) is True

    @pytest.mark.parametrize("filename", ["photo.jpg", "my_photo-1.png", "IMG_0042.WEBP"])
    def test_safe_names_pass(self, filename: str) -> None:
        assert is_unsafe_filename(filename) is False

    def test_validate_filename_rejects_traversal(self, validator: FileValidator) -> None:
        with pytest.raises(InvalidFilenameException) as exc:
            validator.validate_filename("../../secret.txt")
        assert exc.value.error_code == "INVALID_FILENAME"

    def test_validate_filename_sanitizes_safe_names(self, validator: FileValidator) -> None:
        assert validator.validate_filename("my photo.jpg") == "myphoto.jpg"


class TestSizeLimits:
    def test_from_settings_uses_configured_mb(self) -> None:
        assert validator_setting_evidence() == settings.max_evidence_size_mb * 1024 * 1024

    def test_custom_limits(self) -> None:
        custom = FileValidator(
            max_file_sizes_mb={ImageType.EVIDENCE: 2, ImageType.PROGRESS: 1, ImageType.COMPLETION: 1}
        )
        assert custom.max_file_size(ImageType.EVIDENCE) == 2 * 1024 * 1024
        assert custom.max_file_size(ImageType.PROGRESS) == 1 * 1024 * 1024


def validator_setting_evidence() -> int:
    return FileValidator.from_settings(settings).max_file_size(ImageType.EVIDENCE)


class TestReadBounded:
    async def test_reads_content_under_limit(self) -> None:
        payload = JPEG * 10
        assert await read_bounded(FakeReader(payload), 1024) == payload

    async def test_empty_reader(self) -> None:
        assert await read_bounded(FakeReader(b""), 1024) == b""

    async def test_exactly_at_limit_allowed(self) -> None:
        payload = b"x" * 100
        assert await read_bounded(FakeReader(payload), 100) == payload

    async def test_oversized_raises_before_full_buffer(self) -> None:
        payload = b"x" * 1000
        with pytest.raises(FileTooLargeException) as exc:
            await read_bounded(FakeReader(payload), 100)
        assert exc.value.error_code == "FILE_TOO_LARGE"

    async def test_oversized_status_is_400(self) -> None:
        with pytest.raises(FileTooLargeException) as exc:
            await read_bounded(FakeReader(b"y" * 500), 64)
        assert exc.value.status_code == 400
