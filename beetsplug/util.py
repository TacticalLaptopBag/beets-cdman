import re


numbered_track_regex = r"^0*\d+\s+(.*)"


def unnumber_name(name: str) -> str:
    num_check = re.match(numbered_track_regex, name)
    if num_check is not None:
        return num_check.group(1)
    return name
