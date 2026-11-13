"""Read and write times like 1:43.75."""

from __future__ import annotations

MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def parse_time(value: str) -> float:
    """Turn '90', '1:30', or '1:02:03.25' into seconds."""
    text = (value or "").strip()
    if not text:
        raise ValueError("Type a start time and an end time.")
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"This time does not look right: {value}")
    try:
        nums = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"This time does not look right: {value}") from exc
    if any(n < 0 for n in nums):
        raise ValueError("Times cannot be negative.")
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0] * 3600 + nums[1] * 60 + nums[2]


def format_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    whole = int(seconds)
    frac = seconds - whole
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    hundredths = int(round(frac * 100))
    if hundredths == 100:
        hundredths = 0
        secs += 1
        if secs == 60:
            secs = 0
            minutes += 1
            if minutes == 60:
                minutes = 0
                hours += 1
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}.{hundredths:02d}"
    return f"{minutes}:{secs:02d}.{hundredths:02d}"


def date_label(yyyymmdd: str) -> str:
    raw = (yyyymmdd or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 8:
        return raw.upper()[:24]
    year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return raw.upper()[:24]
    return f"{day} {MONTHS[month - 1]} {year}"


def iso_date(yyyymmdd: str) -> str:
    digits = "".join(ch for ch in (yyyymmdd or "") if ch.isdigit())
    if len(digits) < 8:
        return ""
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
