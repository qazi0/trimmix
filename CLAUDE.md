# trimmix

Linux/Ubuntu alternative to macOS Trimmy. Converts multiline shell commands to single-line.

## Setup

```bash
uv sync
uv run pytest tests/ -p no:cacheprovider
```

## Running

```bash
# From clipboard
trimmix

# From stdin
echo "cmd \\\n  --flag" | trimmix -

# Daemon mode
trimmix --daemon
```

## Testing

```bash
PYTHONNOUSERSITE=1 uv run --python 3.11 pytest tests/ -v -p no:cacheprovider
```

Note: ROS packages on this system interfere with pytest. Always use `PYTHONNOUSERSITE=1`.

## Conventions

- Python 3.11+, no external runtime dependencies
- `uv` for package management
- No `from __future__ import annotations`
- No empty exception handlers (`except: pass`)
- Minimize global variables, prefer class encapsulation
- Tests should validate practical behavior, not implementation details
