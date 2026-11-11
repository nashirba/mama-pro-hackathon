from .models import PracticeContext


def is_catalog_visible(context: PracticeContext) -> bool:
    """The single place that decides whether a practice context is shown in the catalog."""
    return context.catalog_enabled
