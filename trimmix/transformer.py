import re
from dataclasses import dataclass

from trimmix.detector import Aggressiveness, CommandDetector


@dataclass
class TransformResult:
    text: str
    original: str
    transformed: bool


_BOX_CHARS = "│┃╎╏┆┇┊┋╽╿￨｜"


class CommandTransformer:
    _BLANK_LINE_PLACEHOLDER = "__TRIMMIX_BLANK__"

    _HYPHEN_WRAPPED = re.compile(r"(?<=[A-Za-z0-9._~-])-\s*\n\s*([A-Za-z0-9._~-])")
    _ALL_CAPS_SPLIT = re.compile(r"(?<!\n)([A-Z0-9_.-])\s*\n\s*([A-Z0-9_.-])(?!\n)")
    _PATH_SPLIT = re.compile(r"(?<=[/~])\s*\n\s*([A-Za-z0-9._-])")
    _BACKSLASH_CONT = re.compile(r"\\\s*\n")
    _NEWLINES = re.compile(r"\n+")
    _MULTI_SPACES = re.compile(r"\s+")
    _BLANK_LINES = re.compile(r"\n\s*\n")

    _URL_SCHEME = re.compile(r"https?://", re.IGNORECASE)
    _URL_VALID = re.compile(r"^https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$")

    _PROMPT_LINE = re.compile(r"^(\s*)[#$]\s*(.*)$")
    _FLAG_AFTER_SPACE = re.compile(r"\s-[A-Za-z]")

    _BOX_DRAWING = re.compile(f"[{_BOX_CHARS}]")
    _BOX_LEADING = re.compile(rf"^\s*[{_BOX_CHARS}]+ ?")
    _BOX_TRAILING = re.compile(rf" ?[{_BOX_CHARS}]+\s*$")
    _BOX_AFTER_PIPE = re.compile(rf"\|\s*[{_BOX_CHARS}]+\s*")
    _BOX_PATH_JOIN = re.compile(rf"([:/])\s*[{_BOX_CHARS}]+\s*([A-Za-z0-9])")
    _BOX_MID_TOKEN = re.compile(rf"(\S)\s*[{_BOX_CHARS}]+\s*(\S)")
    _BOX_ANY_WITH_WS = re.compile(rf"\s*[{_BOX_CHARS}]+\s*")
    _DOUBLE_SPACES = re.compile(r" {2,}")

    def __init__(self, detector: CommandDetector | None = None):
        self._detector = detector or CommandDetector()

    def transform(
        self,
        text: str,
        aggressiveness: Aggressiveness = Aggressiveness.NORMAL,
        preserve_blank_lines: bool = False,
        remove_box_drawing: bool = True,
    ) -> TransformResult:
        if not text or not text.strip():
            return TransformResult(text=text, original=text, transformed=False)

        original = text
        result = text

        if remove_box_drawing:
            cleaned = self._strip_box_drawing(result)
            if cleaned is not None:
                result = cleaned

        stripped = self._strip_prompts(result)
        if stripped is not None:
            result = stripped

        repaired = self._repair_url(result)
        if repaired is not None:
            result = repaired

        quoted = self._quote_path_with_spaces(result)
        if quoted is not None:
            result = quoted

        if self._detector.detect(result, aggressiveness):
            result = self._flatten(result, preserve_blank_lines)

        result = result.strip()
        changed = result != original.strip()
        return TransformResult(text=result, original=original, transformed=changed)

    def _strip_prompts(self, text: str) -> str | None:
        lines = text.splitlines()
        non_empty = [l for l in lines if l.strip()]
        if not non_empty:
            return None

        rebuilt: list[str] = []
        stripped_count = 0
        for line in lines:
            stripped_line = self._try_strip_prompt(line)
            if stripped_line is not None:
                stripped_count += 1
                rebuilt.append(stripped_line)
            else:
                rebuilt.append(line)

        if len(non_empty) == 1:
            should_strip = stripped_count == 1
        else:
            majority_threshold = len(non_empty) // 2 + 1
            should_strip = stripped_count >= majority_threshold

        if not should_strip:
            return None

        new_text = "\n".join(rebuilt)
        return new_text if new_text != text else None

    def _try_strip_prompt(self, line: str) -> str | None:
        m = self._PROMPT_LINE.match(line)
        if not m:
            return None
        leading_ws, rest = m.group(1), m.group(2)
        if not self._looks_like_prompt_command(rest):
            return None
        return leading_ws + rest

    def _looks_like_prompt_command(self, content: str) -> bool:
        trimmed = content.strip()
        if not trimmed:
            return False
        if trimmed[-1] in ".?!":
            return False
        has_cmd_punct = any(c in "-./~$" for c in trimmed) or any(c.isdigit() for c in trimmed)
        first_token = trimmed.split(" ", 1)[0].lower()
        starts_known = any(first_token.startswith(p) for p in self._detector.KNOWN_PREFIXES)
        if not (has_cmd_punct or starts_known):
            return False
        return self._detector._is_likely_command_line(trimmed)

    def _repair_url(self, text: str) -> str | None:
        schemes = self._URL_SCHEME.findall(text)
        if len(schemes) != 1:
            return None
        trimmed = text.strip()
        if not trimmed.lower().startswith(("http://", "https://")):
            return None

        collapsed = re.sub(r"\s+", "", trimmed)
        if collapsed == trimmed:
            return None
        if not self._URL_VALID.match(collapsed):
            return None
        return collapsed

    def _quote_path_with_spaces(self, text: str) -> str | None:
        trimmed = text.strip()
        if not trimmed or "\n" in trimmed:
            return None
        if (trimmed.startswith('"') and trimmed.endswith('"')) or \
           (trimmed.startswith("'") and trimmed.endswith("'")):
            return None
        if "://" in trimmed:
            return None

        first_token = trimmed.split(None, 1)[0] if trimmed.split(None, 1) else ""
        if not first_token:
            return None

        has_explicit_prefix = (
            first_token.startswith("/")
            or first_token.startswith("~/")
            or first_token.startswith("./")
            or first_token.startswith("../")
        )
        looks_relative = "/" in first_token
        if not (has_explicit_prefix or looks_relative):
            return None

        if " " not in trimmed:
            return None

        if self._FLAG_AFTER_SPACE.search(trimmed):
            return None

        escaped = trimmed.replace('"', '\\"')
        return f'"{escaped}"'

    def _strip_box_drawing(self, text: str) -> str | None:
        if not self._BOX_DRAWING.search(text):
            return None

        result = text
        if "│ │" in result:
            result = result.replace("│ │", " ")

        lines = result.split("\n")
        non_empty = [l for l in lines if l.strip()]
        if non_empty:
            majority_threshold = len(non_empty) // 2 + 1
            leading_matches = sum(1 for l in non_empty if self._BOX_LEADING.match(l))
            trailing_matches = sum(1 for l in non_empty if self._BOX_TRAILING.search(l))

            strip_leading = leading_matches >= majority_threshold
            strip_trailing = trailing_matches >= majority_threshold

            if strip_leading or strip_trailing:
                rebuilt: list[str] = []
                for line in lines:
                    s = line
                    if strip_leading:
                        s = self._BOX_LEADING.sub("", s)
                    if strip_trailing:
                        s = self._BOX_TRAILING.sub("", s)
                    rebuilt.append(s)
                result = "\n".join(rebuilt)

        result = self._BOX_AFTER_PIPE.sub("| ", result)
        result = self._BOX_PATH_JOIN.sub(r"\1\2", result)
        result = self._BOX_MID_TOKEN.sub(r"\1 \2", result)
        result = self._BOX_ANY_WITH_WS.sub(" ", result)
        result = self._DOUBLE_SPACES.sub(" ", result)
        result = result.strip()

        return result if result != text.strip() else None

    def _flatten(self, text: str, preserve_blank_lines: bool) -> str:
        result = text

        if preserve_blank_lines:
            result = self._BLANK_LINES.sub(self._BLANK_LINE_PLACEHOLDER, result)

        result = self._HYPHEN_WRAPPED.sub(r"-\1", result)
        result = self._ALL_CAPS_SPLIT.sub(r"\1\2", result)
        result = self._PATH_SPLIT.sub(r"\1", result)
        result = self._BACKSLASH_CONT.sub(" ", result)
        result = self._NEWLINES.sub(" ", result)
        result = self._MULTI_SPACES.sub(" ", result)

        if preserve_blank_lines:
            result = result.replace(self._BLANK_LINE_PLACEHOLDER, "\n\n")

        return result.strip()


_default_transformer = CommandTransformer()


def transform(
    text: str,
    aggressiveness: Aggressiveness = Aggressiveness.NORMAL,
    preserve_blank_lines: bool = False,
    remove_box_drawing: bool = True,
) -> TransformResult:
    return _default_transformer.transform(
        text,
        aggressiveness=aggressiveness,
        preserve_blank_lines=preserve_blank_lines,
        remove_box_drawing=remove_box_drawing,
    )
