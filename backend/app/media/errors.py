"""Domain errors for the media feature.

The router maps these onto the documented ``{"error": {code, message, hint}}``
envelope. No ImageKit SDK type or raw provider message ever escapes this module.
"""

from __future__ import annotations


class MediaError(Exception):
    """Base class for expected media failures."""


class MediaStorageUnavailable(MediaError):
    """ImageKit is not configured, unreachable, or rejected the credentials."""


class MediaStorageFailure(MediaError):
    """ImageKit returned an error for the requested operation."""


class MediaConsistencyError(MediaError):
    """Storage and metadata could not be kept consistent; the request can be retried."""


class MediaNotFound(MediaError):
    """The media record does not exist, is not owned, or has an unexpected path."""


class MediaValidationError(MediaError):
    """The uploaded file failed validation."""


class InvalidMediaType(MediaValidationError):
    """``media_type`` was not ``audio`` or ``image``."""


class UnsupportedMediaType(MediaValidationError):
    """The declared or detected content type is not supported."""


class MediaTooLarge(MediaValidationError):
    """The upload exceeds the configured size limit for its media type."""
