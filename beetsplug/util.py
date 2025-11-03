import re


numbered_track_regex = r"^0*\d+\s+(.*)"


def unnumber_name(name: str) -> str:
    """
    Removes the number prefix from a name, if present
    
    e.g. "01 Track Name" becomes "Track Name"
    """
    num_check = re.match(numbered_track_regex, name)
    if num_check is not None:
        return num_check.group(1)
    return name
