import sys


CLEAR = "\033[K"
MOVE_UP = "\033[F"


class Printer:
    def __init__(self):
        self.lines: list[str] = [""]
        self.current_line = 0
        self.last_line = 0

    def _move_up(self):
        if self.current_line == 0:
            raise RuntimeError("Attempt to move up past known lines")
        sys.stdout.write(MOVE_UP)
        self.current_line -= 1

    def _move_down(self):
        if self.current_line == self.last_line:
            self.last_line += 1
            self.lines.append("\n")
        sys.stdout.write(self.lines[self.current_line])
        self.current_line += 1

    def _move_to_line(self, line_idx: int):
        while self.current_line != line_idx:
            if self.current_line > line_idx:
                self._move_up()
            if self.current_line < line_idx:
                self._move_down()

    def print(self, line_content: str):
        line = self.last_line
        self.print_line(line, line_content)

    def print_line(self, line_idx: int, line_content: str):
        self.print_line_at(line_idx, 0, line_content)

    def print_line_at(self, line_idx: int, column_idx: int, line_content: str):
        if line_idx < 0:
            line_idx = len(self.lines) + line_idx - 1
        self._move_to_line(line_idx)
        sys.stdout.write("\r")
        if column_idx >= len(self.lines[line_idx]):
            self.lines[line_idx] = self.lines[line_idx][:-1]
            sys.stdout.write(self.lines[line_idx])
            for i in range(len(self.lines[line_idx]), column_idx):
                sys.stdout.write(" ")
                self.lines[line_idx] += " "
        else:
            sys.stdout.write(self.lines[line_idx][:column_idx])
            self.lines[line_idx] = self.lines[line_idx][:column_idx]
        sys.stdout.write(CLEAR)
        sys.stdout.write(line_content+"\n")
        self.lines[line_idx] += line_content+"\n"
        if self.current_line == self.last_line:
            self.last_line += 1
            self.lines.append("\n")
        self.current_line += 1
        sys.stdout.flush()

    def __del__(self):
        # Terminal prompt will overwrite the last line we were on,
        # make sure we move to the very last line to not overwrite output
        self._move_to_line(self.last_line)
    

if __name__ == "__main__":
    p = Printer()
    p.print("Line 0")
    p.print("Line 1")
    p.print("Line 2")

    p.print_line(0, "LINE 0")
    p.print_line(2, "LINE 2")
    p.print_line(1, "LINE 1")
    p.print_line(5, "Line 5")
    p.print_line(1, "Line 1 is long now")
    p.print_line(2, "li 2")

    p.print_line_at(1, 5, "one has changed")
    p.print_line_at(0, 10, "Zero has spaces!")
    p.print_line_at(4, 15, "new")
