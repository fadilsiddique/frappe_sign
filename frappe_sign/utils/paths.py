"""File path helpers."""

PRIVATE_FILES_PREFIX = "/private/files/"


def is_private_file_url(file_url: str | None) -> bool:
	return bool(file_url) and file_url.startswith(PRIVATE_FILES_PREFIX)
