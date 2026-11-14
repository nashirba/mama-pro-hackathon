def lowest(items, column: str) -> int | None:
    """The lowest non-empty value of `column` among services or search offers."""
    values = [getattr(i, column) for i in items if getattr(i, column) is not None]
    return min(values) if values else None
