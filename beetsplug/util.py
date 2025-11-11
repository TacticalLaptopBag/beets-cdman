from pathlib import Path
import re
import subprocess
import sys

from beetsplug.config import Config


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


def ffmpeg(source: Path, destination: Path, args: list[str] = []) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(source),
            "-hide_banner",
        ] + args + [
            str(destination)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Check that the conversion actually went through
    if result.returncode != 0:
        if Config.verbose:
            sys.stderr.write(f"Error converting `{source}`! Look in `{destination.parent}` for ffmpeg logs.\n")

        # Create error logs in place of where the track should've been
        stdout_log_path = destination.with_suffix(".stdout.log")
        stderr_log_path = destination.with_suffix(".stderr.log")
        with stdout_log_path.open("wb") as stdout_log:
            stdout_log.write(result.stdout)
        with stderr_log_path.open("wb") as stderr_log:
            stderr_log.write(result.stderr)
    return result
