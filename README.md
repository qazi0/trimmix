# trimmix

Flatten multi-line shell commands copied to your clipboard so they paste and run as a single line on Linux.

Inspired by and a faithful Python port of [Peter Steinberger's Trimmy](https://github.com/steipete/Trimmy) for macOS. No Swift runtime required; pure Python 3.11+, no runtime dependencies.

## Why

You paste a command like this from a blog, GitHub issue, or LLM output:

```
docker run -d \
  --name nginx \
  -p 8080:80 \
  nginx:latest
```

and the terminal either refuses to run it or runs each line separately. trimmix rewrites the clipboard so the same command becomes:

```
docker run -d --name nginx -p 8080:80 nginx:latest
```

Bind it to a GNOME keyboard shortcut and it pastes the cleaned command into the focused window with a single keypress.

## Install (Ubuntu 22.04+)

```bash
curl -fsSL https://raw.githubusercontent.com/qazi0/trimmix/main/install.sh | bash
```

The installer will:

1. `sudo apt install` the runtime dependencies (`git`, `python3.11`, `python3.11-venv`, `wl-clipboard`, `ydotool`, `ydotoold`).
2. Clone trimmix into `~/.local/share/trimmix` and create a venv there.
3. Symlink the binary at `~/.local/bin/trimmix`.
4. Install and enable a user-level systemd service for `ydotoold` (needed for autopaste into Wayland apps).
5. Warn if `~/.local/bin` is missing from `PATH` or if `/dev/uinput` lacks ACL access.

Re-running is idempotent.

## Usage

### One-shot from clipboard

```bash
trimmix                # transform clipboard in place
trimmix --paste        # transform and auto-paste Ctrl+V
trimmix --paste -t     # transform and auto-paste Ctrl+Shift+V (for terminals)
```

### From stdin

```bash
printf 'kubectl get pods\n  --namespace prod\n  -o wide' | trimmix -
```

### Flags

| Flag | Purpose |
|---|---|
| `--aggressiveness {low,normal,high}`, `-a` | Detection threshold (default: `normal`) |
| `--force`, `-f` | Force high aggressiveness |
| `--preserve-blank-lines` | Keep blank lines inside flattened output |
| `--keep-box-drawing` | Do not strip `│┃╎` etc. (default: stripped) |
| `--paste`, `-p` | Auto-paste after transforming |
| `--terminal`, `-t` | Paste via Ctrl+Shift+V instead of Ctrl+V |
| `--quiet`, `-q` | Suppress progress output |

### GNOME keyboard shortcuts

Open `Settings > Keyboard > View and Customize Shortcuts > Custom Shortcuts` and add two shortcuts so one works in terminals and the other in editors and browsers:

| Key combo | Command | Target |
|---|---|---|
| `Alt+Shift+T` | `trimmix --paste --terminal --quiet` | Terminals |
| `Alt+Shift+V` | `trimmix --paste --quiet` | Editors, browsers, Slack, etc. |

If the shortcut does nothing when pressed, `~/.local/bin` may not be on the PATH that GNOME passes to custom shortcuts. Either log out and back in so the systemd user session picks up `~/.profile`, or use the full path in the command: `/home/<user>/.local/bin/trimmix --paste ...`.

Avoid `Ctrl+V` or `Ctrl+Shift+V` for the shortcut combo itself, or the synthetic keypress that trimmix injects can re-trigger the shortcut.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Transformed or pasted successfully |
| 1 | Error reading or writing the clipboard, or auto-paste failed |
| 2 | No transformation needed and `--paste` was not requested |

## What gets transformed

trimmix mirrors Trimmy's heuristics (same score thresholds, same flatten regexes) plus a Linux-leaning `KNOWN_PREFIXES` list:

1. Box-drawing characters (`│┃╎╏┆┇┊┋╽╿￨｜`) from tables and boxed output are stripped.
2. Leading `#` or `$` shell prompts are removed when the remainder looks like a command.
3. Wrapped URLs that span lines are rejoined into a single valid URL.
4. Paths containing spaces (e.g. `/Users/me/My Folder/file.txt`) are wrapped in double quotes.
5. Multi-line shell commands are detected by a 7-signal score (backslash continuations, pipes or logical operators, `$` prompt, indented continuation shape, all-lines-look-like-commands, known command prefix, path-like tokens) and flattened to a single line if the score meets the aggressiveness threshold.

Known divergences from Trimmy (intentional):

- trimmix allows commands longer than 4 lines at normal aggressiveness if they contain `\` continuations. Trimmy rejects them unless aggressiveness is high.
- trimmix's "independent commands" reject gate preserves indented-continuation commands (e.g. `kubectl get pods` followed by indented flags) that Trimmy would otherwise reject.

## Requirements

- Ubuntu 22.04+ (or equivalent with Python 3.11, systemd, Wayland or X11).
- GNOME on Wayland is the primary target. X11 sessions and other Wayland compositors also work as long as the corresponding input-injection tool is available.

### Why ydotool and not wtype or xdotool

- `wtype` uses the `virtual-keyboard-unstable-v1` Wayland protocol, which GNOME Mutter does not implement, so it fails on GNOME. It works on sway, hyprland, and other wlroots compositors.
- `xdotool` is X11-only. Under Wayland it runs through XWayland and cannot inject keys into native Wayland windows.
- `ydotool` uses the Linux kernel `uinput` interface, which works on every Linux desktop regardless of compositor. It requires a running `ydotoold` daemon, which the installer sets up as a user systemd service.

## Development

```bash
uv sync
PYTHONNOUSERSITE=1 uv run --python 3.11 pytest tests/ -p no:cacheprovider
```

`PYTHONNOUSERSITE=1` is required because ROS system Python packages register a broken pytest plugin on some distros.

## Credits

- Algorithm and heuristics: [Trimmy by Peter Steinberger](https://github.com/steipete/Trimmy) (Swift, macOS + `TrimmyCLI`).
- `wl-clipboard`: [bugaevc/wl-clipboard](https://github.com/bugaevc/wl-clipboard).
- `ydotool` / `ydotoold`: [ReimuNotMoe/ydotool](https://github.com/ReimuNotMoe/ydotool).

## License

MIT.
