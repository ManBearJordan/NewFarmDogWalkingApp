from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def calendar_day_dots(calendar_days, day):
    """Generate HTML for calendar day dots."""
    if day not in calendar_days:
        return ""
    
    counts = calendar_days[day]
    dots_html = []
    
    if counts.get('bookings', 0) > 0:
        dots_html.append(
            f'<span class="dot dot-blue" title="{counts["bookings"]} booking{"s" if counts["bookings"] > 1 else ""}">'
            f'{counts["bookings"]}</span>'
        )
    
    if counts.get('sub_occurrences', 0) > 0:
        dots_html.append(
            f'<span class="dot dot-purple" title="{counts["sub_occurrences"]} subscription{"s" if counts["sub_occurrences"] > 1 else ""}">'
            f'{counts["sub_occurrences"]}</span>'
        )
    
    if counts.get('admin_events', 0) > 0:
        dots_html.append(
            f'<span class="dot dot-orange" title="{counts["admin_events"]} admin event{"s" if counts["admin_events"] > 1 else ""}">'
            f'{counts["admin_events"]}</span>'
        )
    
    return mark_safe(''.join(dots_html))

@register.simple_tag
def format_date_key(year, month, day):
    """Format a date key for URL parameters."""
    return f"{year}-{month:02d}-{day:02d}"