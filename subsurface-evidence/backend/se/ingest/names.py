"""One spelling for a wellbore name, same rule as the hackathon app: 'NO 15/9-F- 12' -> '15/9-F-12'."""
import re


def norm(name) -> str:
    s = re.sub(r"^\s*NO\s+", "", str(name).upper()).strip()
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s)
