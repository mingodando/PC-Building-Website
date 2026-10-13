from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def baht(value):
    """Format a number as Thai baht: 15000 -> ฿15,000 and 99.5 -> ฿99.50."""
    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    if value == value.to_integral_value():
        return f"฿{value:,.0f}"
    return f"฿{value:,.2f}"


@register.simple_tag(takes_context=True)
def query_with(context, **kwargs):
    """Current query string with some parameters replaced, e.g. {% query_with page=2 %}."""
    params = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            params.pop(key, None)
        else:
            params[key] = value
    # Changing a filter should send you back to the first page of results.
    if 'page' not in kwargs:
        params.pop('page', None)
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else '?'
