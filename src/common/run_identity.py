"""Technical run identity helpers."""

from datetime import UTC, datetime


def create_run_id(prefix: str = "run") -> str:
    """Create a filesystem-safe run id using UTC time."""
    safe_prefix = "".join(
        character for character in prefix if character.isalnum() or character == "_"
    )
    if not safe_prefix:
        safe_prefix = "run"

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{safe_prefix}_{timestamp}"
