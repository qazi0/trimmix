import argparse
import sys

from trimmix import __version__
from trimmix.clipboard import Clipboard, ClipboardError
from trimmix.detector import Aggressiveness
from trimmix.paste import PasteError, paste
from trimmix.transformer import transform


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="trimmix",
        description="Convert multiline shell commands to single-line",
    )
    parser.add_argument("--version", action="version", version=f"trimmix {__version__}")
    parser.add_argument(
        "--aggressiveness", "-a",
        choices=["low", "normal", "high"],
        default="normal",
    )
    parser.add_argument("--preserve-blank-lines", action="store_true")
    parser.add_argument("--keep-box-drawing", action="store_true", help="Do not strip box-drawing characters (default: stripped)")
    parser.add_argument("--force", "-f", action="store_true", help="Force high aggressiveness")
    parser.add_argument("--paste", "-p", action="store_true", help="Simulate Ctrl+V paste after transforming")
    parser.add_argument("--terminal", "-t", action="store_true", help="Use Ctrl+Shift+V for pasting (for terminals)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")
    parser.add_argument(
        "input", nargs="?", type=argparse.FileType("r"), default=None,
        help="Read from file/stdin instead of clipboard (use - for stdin)",
    )

    args = parser.parse_args()
    aggressiveness = Aggressiveness.HIGH if args.force else Aggressiveness[args.aggressiveness.upper()]

    if args.input:
        text = args.input.read()
    else:
        try:
            clipboard = Clipboard()
            text = clipboard.read()
        except ClipboardError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    result = transform(
        text,
        aggressiveness=aggressiveness,
        preserve_blank_lines=args.preserve_blank_lines,
        remove_box_drawing=not args.keep_box_drawing,
    )

    if args.input:
        if not result.transformed:
            if not args.quiet:
                print("No transformation needed.", file=sys.stderr)
            return 2
        print(result.text)
        return 0

    if result.transformed:
        try:
            clipboard = Clipboard()
            clipboard.write(result.text)
        except ClipboardError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if not args.quiet:
            print("Transformed and copied to clipboard:", file=sys.stderr)
            print(result.text, file=sys.stderr)
    elif not args.paste:
        if not args.quiet:
            print("No transformation needed.", file=sys.stderr)
        return 2

    if args.paste:
        try:
            paste(terminal=args.terminal)
        except PasteError as e:
            print(f"Auto-paste failed: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
