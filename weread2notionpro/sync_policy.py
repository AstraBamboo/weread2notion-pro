import math


def eligible_duration(value):
    """Compare the exact numeric value written to Notion; never coerce strings."""
    return type(value) in (int, float) and math.isfinite(value) and value > 500
