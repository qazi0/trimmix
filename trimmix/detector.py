import re
from enum import IntEnum


class Aggressiveness(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2

    @property
    def score_threshold(self) -> int:
        return {self.LOW: 3, self.NORMAL: 2, self.HIGH: 1}[self]


class CommandDetector:
    KNOWN_PREFIXES = frozenset([
        "apt", "brew", "pip", "pip3", "npm", "npx", "yarn", "pnpm", "cargo",
        "bundle", "rails", "git", "make", "go", "gradle", "swift", "xcodebuild",
        "docker", "podman", "kubectl", "aws", "gcloud", "az", "terraform",
        "bash", "zsh", "fish", "pwsh", "sh",
        "echo", "cat", "ls", "cd", "curl", "ssh", "wget", "tar", "find",
        "grep", "sed", "awk", "sort", "uniq", "head", "tail", "wc", "xargs",
        "tee", "env", "export", "source", "open", "cp", "mv", "rm", "mkdir",
        "python", "python3", "ruby", "node", "java", "perl",
        "mvn", "cmake", "gcc", "clang", "rustc",
        "systemctl", "journalctl", "snap", "flatpak",
        "chmod", "chown", "ln", "mount", "umount",
        "uv", "uvx", "pipx", "conda",
    ])

    _SOURCE_CODE_KEYWORDS = re.compile(
        r"\b(import|from|class|func|def|struct|enum|interface|var|let|const|return|"
        r"if|else|for|while|switch|case|try|catch|throw|async|await|pub|fn|impl|use|mod)\b"
    )
    _BRACE_OR_BEGIN = re.compile(r"[{}]|\bbegin\b|\bend\b")
    _BULLET_PATTERN = re.compile(r"^[-*•]\s+\S")
    _NUMBERED_PATTERN = re.compile(r"^[0-9]+[.)]\s+\S")
    _BARE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9]{4,}$")
    _BACKSLASH_CONTINUATION = re.compile(r"\\\s*\n")
    _PIPE_OR_LOGIC = re.compile(r"\|(?!\|)|\|\||&&")
    _PROMPT_LINE = re.compile(r"^\s*[#$]\s+\S")
    _DOLLAR_PROMPT = re.compile(r"(?:^|\n)\s*\$")
    _PATH_PATTERN = re.compile(r"[A-Za-z0-9._~-]+/[A-Za-z0-9._~-]+")
    _COMMAND_START = re.compile(r"^(?:sudo\s+)?[A-Za-z0-9./~_-]+(?:\s|$)")
    _PROMPT_PREFIX = re.compile(r"^[#$]\s+")
    _OPERATOR_START = re.compile(r"^\s*(\||&&|\|\||;|>|2>|<|--|-[A-Za-z])")

    _EOL_LINE_JOINER = re.compile(r"(?m)(\\|[|&]{1,2}|;)\s*$")
    _INDENTED_PIPELINE = re.compile(r"(?m)^\s*[|&]{1,2}\s+\S")

    _CMD_PUNCT_LONG_FLAG = re.compile(r"(?:^|\s)--[A-Za-z0-9][A-Za-z0-9_-]*", re.MULTILINE)
    _CMD_PUNCT_SHORT_FLAG = re.compile(r"(?:^|\s)-[A-Za-z](?:\s|$)", re.MULTILINE)
    _CMD_PUNCT_VAR_ASSIGN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*=", re.MULTILINE)
    _CMD_PUNCT_PATH_START = re.compile(r"(?:^|\s)(?:\./|~/|/)", re.MULTILINE)
    _CMD_PUNCT_DOT_NAME = re.compile(r"(?:^|\s)\.[A-Za-z0-9_-]+", re.MULTILINE)

    _LINE_LONG_FLAG = re.compile(r"--[A-Za-z0-9_-]+")
    _LINE_SHORT_FLAG = re.compile(r"\s-[A-Za-z](?:\s|$)")
    _LINE_VAR_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")

    def detect(self, text: str, aggressiveness: Aggressiveness = Aggressiveness.NORMAL) -> bool:
        if not text or not text.strip():
            return False

        lines = text.strip().splitlines()
        non_empty = [l for l in lines if l.strip()]

        if len(non_empty) < 2:
            return False
        if len(non_empty) > 10:
            return False

        has_continuations = bool(self._BACKSLASH_CONTINUATION.search(text))
        if len(non_empty) > 4 and aggressiveness != Aggressiveness.HIGH and not has_continuations:
            return False

        if self._is_likely_list(non_empty) and aggressiveness != Aggressiveness.HIGH:
            return False

        if (
            self._is_likely_source_code(text)
            and aggressiveness != Aggressiveness.HIGH
            and not has_continuations
        ):
            return False

        has_explicit_join = self._has_explicit_line_join(text)
        all_command_lines = all(self._is_likely_command_line(l) for l in non_empty)
        indented_cont = self._is_indented_continuation(non_empty)

        if (
            aggressiveness != Aggressiveness.HIGH
            and not has_explicit_join
            and all_command_lines
            and len(non_empty) >= 3
            and not indented_cont
        ):
            return False

        strong_signals = (
            has_continuations
            or bool(self._PIPE_OR_LOGIC.search(text))
            or bool(self._DOLLAR_PROMPT.search(text))
            or bool(self._PATH_PATTERN.search(text))
        )
        has_known_prefix = any(self._starts_with_known_command(l) for l in non_empty)
        has_cmd_punct = self._text_has_command_punctuation(text)

        if (
            aggressiveness != Aggressiveness.HIGH
            and not strong_signals
            and not has_known_prefix
            and not has_cmd_punct
        ):
            return False

        score = 0
        if has_continuations:
            score += 1
        if self._PIPE_OR_LOGIC.search(text):
            score += 1
        if self._has_prompt_prefix(non_empty):
            score += 1
        if indented_cont:
            score += 1
        if all_command_lines:
            score += 1
        if self._starts_with_known_command(non_empty[0]):
            score += 1
        if self._PATH_PATTERN.search(text):
            score += 1

        return score >= aggressiveness.score_threshold

    def _has_explicit_line_join(self, text: str) -> bool:
        if self._BACKSLASH_CONTINUATION.search(text):
            return True
        if self._EOL_LINE_JOINER.search(text):
            return True
        if self._INDENTED_PIPELINE.search(text):
            return True
        return False

    def _text_has_command_punctuation(self, text: str) -> bool:
        if "@" in text:
            return True
        if self._CMD_PUNCT_LONG_FLAG.search(text):
            return True
        if self._CMD_PUNCT_SHORT_FLAG.search(text):
            return True
        if self._CMD_PUNCT_VAR_ASSIGN.search(text):
            return True
        if self._CMD_PUNCT_PATH_START.search(text):
            return True
        if self._CMD_PUNCT_DOT_NAME.search(text):
            return True
        if "<" in text or ">" in text:
            return True
        return False

    def _strip_prompt(self, line: str) -> str:
        stripped = line.strip()
        m = self._PROMPT_PREFIX.match(stripped)
        return stripped[m.end():] if m else stripped

    def _is_likely_list(self, lines: list[str]) -> bool:
        if len(lines) < 2:
            return False
        threshold = len(lines) // 2 + 1
        bullet_or_numbered = sum(
            1 for l in lines
            if self._BULLET_PATTERN.match(l.strip())
            or self._NUMBERED_PATTERN.match(l.strip())
        )
        if bullet_or_numbered >= threshold:
            return True
        if len(lines) >= 3:
            bare_count = sum(
                1 for l in lines
                if self._BARE_TOKEN_PATTERN.match(l.strip())
                and l.strip().lower() not in self.KNOWN_PREFIXES
            )
            if bare_count >= threshold:
                return True
        return False

    def _is_likely_source_code(self, text: str) -> bool:
        return bool(self._BRACE_OR_BEGIN.search(text) and self._SOURCE_CODE_KEYWORDS.search(text))

    def _has_prompt_prefix(self, lines: list[str]) -> bool:
        count = sum(1 for l in lines if self._PROMPT_LINE.match(l))
        return count >= len(lines) * 0.5

    def _is_indented_continuation(self, lines: list[str]) -> bool:
        if len(lines) < 2:
            return False
        if not self._is_likely_command_line(lines[0]):
            return False
        if lines[0][0:1].isspace():
            return False

        has_indented = False
        for l in lines[1:]:
            if not l.strip():
                continue
            if l[0:1].isspace() or self._OPERATOR_START.match(l):
                has_indented = True
            else:
                return False
        return has_indented

    def _is_likely_command_line(self, line: str) -> bool:
        stripped = self._strip_prompt(line)
        if not stripped:
            return False
        if stripped.endswith(".") and not stripped.endswith(".."):
            return False
        if self._COMMAND_START.match(stripped):
            return True
        if stripped.startswith("[["):
            return True
        return self._line_has_command_punctuation(stripped)

    def _line_has_command_punctuation(self, text: str) -> bool:
        return bool(
            self._LINE_LONG_FLAG.search(text)
            or self._LINE_SHORT_FLAG.search(text)
            or self._LINE_VAR_ASSIGN.search(text)
            or text.startswith("./")
            or text.startswith("~/")
            or text.startswith("/")
            or any(c in text for c in "<>@")
        )

    def _starts_with_known_command(self, line: str) -> bool:
        stripped = self._strip_prompt(line)
        if stripped.startswith("sudo "):
            stripped = stripped[5:].lstrip()
        first_word = re.split(r"[\s/]", stripped)[0] if stripped else ""
        if first_word in self.KNOWN_PREFIXES:
            return True
        return stripped.startswith("./") or stripped.startswith("~/")


_default_detector = CommandDetector()


def detect_command(text: str, aggressiveness: Aggressiveness = Aggressiveness.NORMAL) -> bool:
    return _default_detector.detect(text, aggressiveness)
