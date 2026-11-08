"""Internal database failures, mapped to documented API errors by the router."""

from __future__ import annotations


class RecipeNotFound(Exception):
    """A recipe does not exist or is not owned by the authenticated user."""


class InvalidPersonLink(Exception):
    """A cook/narrator person id was supplied, but person management is postponed."""


class DatabaseUnavailable(Exception):
    """Supabase was unreachable or timed out."""


class DatabaseFailure(Exception):
    """Supabase returned an unexpected or failed response."""
