"""Consistent human-readable minute formatting."""


def format_minutes(minutes: int) -> str:
    minutes = max(int(minutes), 0)
    return f"{minutes // 60} 小時 {minutes % 60} 分"
