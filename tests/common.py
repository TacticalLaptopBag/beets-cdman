from pathlib import Path


file_path = Path(__file__)
music_path = file_path.parent / "music"
assert music_path.exists()