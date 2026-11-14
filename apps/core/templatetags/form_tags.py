from django import template

register = template.Library()


@register.filter
def with_errors(field):
    """Render a bound field with `aria-invalid` and `aria-describedby` pointing at its error block
    (`<auto_id>-error`) when it has errors; otherwise render it unchanged."""
    if not field.errors:
        return field
    return field.as_widget(attrs={"aria-invalid": "true", "aria-describedby": f"{field.auto_id}-error"})
