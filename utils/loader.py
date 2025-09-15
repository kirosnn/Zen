import sys
import time
from typing import Optional


class SingleBrailleLoader:
    _levels = ["⠀", "⠁", "⠃", "⠇", "⡇", "⣇", "⣧", "⣷", "⣿"]
    _max_level = len(_levels) - 1
    _GREEN = "\033[92m"
    _RESET = "\033[0m"

    def __init__(self, total: int, stream: Optional[sys.stdout] = None):
        self.total = total
        self.stream = stream or sys.stdout
        self.current = 0
        self.start_time = time.time()
        self._finished = False
        self.status = ""

    def update(self, step: int = 1) -> None:
        self.current = min(self.total, self.current + step)
        self._render()

    def _render(self) -> None:
        if self._finished:
            return

        progress = self.current / self.total if self.total > 0 else 1.0
        idx = int(round(progress * self._max_level))

        elapsed = time.time() - self.start_time
        eta = (elapsed / progress) - elapsed if progress > 0 else 0

        percent = int(progress * 100)
        elapsed_str = f"{elapsed:.1f}s"

        if self.current >= self.total:
            char = f"{self._GREEN}{self._levels[-1]}{self._RESET}"
            eta_str = "done"
            status_to_print = self.status
            status_str = ""
        else:
            char = self._levels[idx]
            eta_str = f"{eta:.1f}s" if eta < 3600 else f"{eta/3600:.1f}h"
            status_to_print = ""
            status_str = f" {self.status}" if self.status else ""

        self.stream.write(f"\r{char} {percent:3d}% [{elapsed_str}<{eta_str}]{status_str}")
        self.stream.flush()

        if self.current >= self.total:
            self._finished = True
            self.stream.write('\n')
            if status_to_print:
                self.stream.write(f"{status_to_print}\n")
                self.stream.flush()

    def start(self) -> None:
        pass

    def set_status(self, status: str) -> None:
        self.status = status
        self._render()

    def finish(self) -> None:
        self.stop()

    def stop(self) -> None:
        pass