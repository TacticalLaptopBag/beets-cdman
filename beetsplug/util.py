from pathlib import Path

import ffmpeg


def get_song_length(path: Path) -> float:
    try:
        probe = ffmpeg.probe(str(path))
    except ffmpeg.Error:
        return 0.0

    stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)
    if stream is None:
        return 0.0

    duration = float(stream["duration"])
    return duration


def get_all_files(directory: Path) -> list[Path]:
    return [Path(walk_listing[0] / file) for walk_listing in directory.walk() for file in walk_listing[2]]


def get_directory_size(directory: Path) -> int:
    files = get_all_files(directory)
    file_sizes = [file.stat().st_size for file in files]
    return sum(file_sizes)


def get_directory_audio_length(directory: Path) -> float:
    files = get_all_files(directory)
    audio_files = list(filter(lambda f: f.suffix == ".mp3", files))
    durations = [get_song_length(audio_file) for audio_file in audio_files]
    return sum(durations)

