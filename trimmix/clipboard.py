import shutil
import subprocess


class ClipboardError(RuntimeError):
    pass


class Clipboard:
    def __init__(self):
        self._read_cmd = self._find_read_tool()
        self._write_cmd = self._find_write_tool()

    def _find_read_tool(self) -> list[str]:
        if shutil.which("wl-paste"):
            return ["wl-paste", "--no-newline"]
        if shutil.which("xclip"):
            return ["xclip", "-o", "-selection", "clipboard"]
        raise ClipboardError("No clipboard tool found. Install wl-clipboard or xclip.")

    def _find_write_tool(self) -> list[str]:
        if shutil.which("wl-copy"):
            return ["wl-copy"]
        if shutil.which("xclip"):
            return ["xclip", "-i", "-selection", "clipboard"]
        raise ClipboardError("No clipboard tool found. Install wl-clipboard or xclip.")

    def read(self) -> str:
        try:
            result = subprocess.run(
                self._read_cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired as e:
            raise ClipboardError(f"Clipboard read timed out: {e}") from e
        except FileNotFoundError as e:
            raise ClipboardError(f"Clipboard tool not found: {e}") from e

        if result.returncode != 0:
            raise ClipboardError(f"Clipboard read failed: {result.stderr.strip()}")

        return result.stdout.replace("\r\n", "\n")

    def write(self, text: str) -> None:
        # wl-copy forks a daemon that serves the clipboard; if we capture
        # its stdout/stderr, the daemon inherits the pipes and Python hangs
        # waiting for them to close. Route to /dev/null so the daemon can
        # detach cleanly.
        try:
            result = subprocess.run(
                self._write_cmd,
                input=text,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except subprocess.TimeoutExpired as e:
            raise ClipboardError(f"Clipboard write timed out: {e}") from e
        except FileNotFoundError as e:
            raise ClipboardError(f"Clipboard tool not found: {e}") from e

        if result.returncode != 0:
            raise ClipboardError(f"Clipboard write failed (exit {result.returncode})")
