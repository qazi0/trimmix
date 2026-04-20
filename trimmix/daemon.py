import hashlib
import os
import signal
import subprocess
import sys
import tempfile
import time

from trimmix.clipboard import Clipboard, ClipboardError
from trimmix.detector import Aggressiveness
from trimmix.transformer import transform


class Daemon:
    HASH_FILE = os.path.join(tempfile.gettempdir(), "trimmix-last-hash")

    def __init__(self, aggressiveness: Aggressiveness = Aggressiveness.NORMAL, preserve_blank_lines: bool = False):
        self._aggressiveness = aggressiveness
        self._preserve_blank_lines = preserve_blank_lines
        self._clipboard = Clipboard()
        self._running = True

    def run(self) -> int:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        print("trimmix daemon started. Watching clipboard...", file=sys.stderr)
        print(f"  aggressiveness: {self._aggressiveness.name.lower()}", file=sys.stderr)
        print("  Press Ctrl+C to stop.", file=sys.stderr)

        try:
            self._watch_loop()
        except KeyboardInterrupt:
            pass

        print("\ntrimmix daemon stopped.", file=sys.stderr)
        return 0

    def _watch_loop(self) -> None:
        while self._running:
            proc = subprocess.Popen(
                ["wl-paste", "--type", "text/plain", "--watch", "cat"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            try:
                self._read_events(proc)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()

            if self._running:
                time.sleep(1)

    def _read_events(self, proc: subprocess.Popen) -> None:
        while self._running and proc.poll() is None:
            # wl-paste --watch cat outputs clipboard content each time it changes.
            # Read all available data until we get a timeout (no more data = event complete)
            proc.stdout.flush()
            content = self._read_until_pause(proc)
            if content:
                self._handle_change(content.decode("utf-8", errors="replace"))

    def _read_until_pause(self, proc: subprocess.Popen) -> bytes:
        """Read from proc stdout until no data arrives for a short window."""
        import select
        chunks = []
        while True:
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if not ready:
                break
            data = proc.stdout.read1(4096) if hasattr(proc.stdout, 'read1') else os.read(proc.stdout.fileno(), 4096)
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks)

    def _handle_change(self, text: str) -> None:
        text = text.replace("\r\n", "\n").rstrip("\n")
        if not text.strip():
            return

        text_hash = hashlib.sha256(text.encode()).hexdigest()
        if text_hash == self._read_last_hash():
            return

        result = transform(text, self._aggressiveness, self._preserve_blank_lines)
        if not result.transformed:
            return

        result_hash = hashlib.sha256(result.text.encode()).hexdigest()
        self._write_last_hash(result_hash)

        try:
            self._clipboard.write(result.text)
            preview = result.text[:80] + ("..." if len(result.text) > 80 else "")
            print(f"  Transformed: {preview}", file=sys.stderr)
        except ClipboardError as e:
            print(f"  Error: {e}", file=sys.stderr)

    def _read_last_hash(self) -> str | None:
        try:
            with open(self.HASH_FILE) as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    def _write_last_hash(self, h: str) -> None:
        with open(self.HASH_FILE, "w") as f:
            f.write(h)

    def _handle_signal(self, signum, frame):
        self._running = False
