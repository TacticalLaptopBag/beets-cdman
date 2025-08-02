from pathlib import Path


class CDFolder:
    def __init__(self, item_dict: dict[str, str]):
        self.dirname = item_dict["name"]
        self.query = item_dict["query"]

    def get_path(self, idx: int, cd_path: Path, total_count: int) -> Path:
        padding = len(str(total_count))
        padded_idx = str(idx + 1).rjust(padding, "0")
        indexed_dirname = f"{padded_idx} {self.dirname}"
        return cd_path / indexed_dirname

    def __str__(self) -> str:
        return f"{self.dirname}: {self.query}"
