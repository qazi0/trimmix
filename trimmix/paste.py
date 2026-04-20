import os
import shutil
import subprocess
import time


class PasteError(RuntimeError):
    pass


_COMMANDS = {
    ("ydotool", "ctrl+v"): ["ydotool", "key", "ctrl+v"],
    ("ydotool", "ctrl+shift+v"): ["ydotool", "key", "ctrl+shift+v"],
    ("wtype", "ctrl+v"): ["wtype", "-M", "ctrl", "v", "-m", "ctrl"],
    ("wtype", "ctrl+shift+v"): ["wtype", "-M", "ctrl", "-M", "shift", "v", "-m", "shift", "-m", "ctrl"],
    ("xdotool", "ctrl+v"): ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
    ("xdotool", "ctrl+shift+v"): ["xdotool", "key", "--clearmodifiers", "ctrl+shift+v"],
}


def paste(delay: float = 0.15, env=None, terminal: bool = False) -> None:
    """Send a paste shortcut to the focused window.

    terminal=True sends Ctrl+Shift+V (what terminals expect); otherwise
    Ctrl+V (what editors, browsers, and most apps expect).

    ydotool is preferred on Wayland because it uses the kernel uinput
    interface and works on every compositor. wtype only works on
    compositors that implement virtual-keyboard-unstable-v1 (not GNOME).
    xdotool remains as an XWayland fallback.
    """
    env = env if env is not None else os.environ
    is_wayland = bool(env.get("WAYLAND_DISPLAY"))

    candidates = ("ydotool", "wtype", "xdotool") if is_wayland else ("xdotool",)
    tool = next((t for t in candidates if shutil.which(t)), None)

    if tool is None:
        if is_wayland:
            raise PasteError(
                "No Wayland paste tool found. Install one of:\n"
                "  sudo apt install ydotool ydotoold   (recommended on GNOME)\n"
                "  sudo apt install wtype              (wlroots compositors only)\n"
                "xdotool alone cannot paste into native Wayland apps."
            )
        raise PasteError("xdotool not found. Install with: sudo apt install xdotool")

    if delay > 0:
        time.sleep(delay)

    combo = "ctrl+shift+v" if terminal else "ctrl+v"
    result = subprocess.run(_COMMANDS[(tool, combo)], capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        raise PasteError(f"Paste via {tool} failed: {result.stderr.strip()}")
