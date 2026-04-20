import pytest
from trimmix.transformer import transform
from trimmix.detector import Aggressiveness


class TestTransformations:
    def test_backslash_continuations(self):
        text = "docker run -d \\\n  --name my-container \\\n  -p 8080:80 \\\n  nginx:latest"
        assert transform(text).text == "docker run -d --name my-container -p 8080:80 nginx:latest"

    def test_indented_continuations(self):
        text = "kubectl get pods\n  --namespace production\n  -o wide"
        assert transform(text).text == "kubectl get pods --namespace production -o wide"

    def test_hyphen_wrapped_uuid(self):
        text = "open scan-qr-f1cc4328-eb1d-4a3c-9bd2-\n  f1a4ccda5f6a.png"
        assert transform(text).text == "open scan-qr-f1cc4328-eb1d-4a3c-9bd2-f1a4ccda5f6a.png"

    def test_prompt_stripping(self):
        result = transform("$ echo hi\n$ ls -la")
        assert "$ " not in result.text
        assert "echo" in result.text and "ls" in result.text

    def test_url_repair(self):
        text = "https://example.com/some-\n path?foo=1&bar= two"
        assert transform(text).text == "https://example.com/some-path?foo=1&bar=two"


class TestNoOps:
    @pytest.mark.parametrize("text", [
        "ls -la",
        "",
        "Meeting notes:\nDiscuss the API.\nReview PRs.",
        "https://example.com/already-clean",
    ])
    def test_no_transformation_needed(self, text):
        result = transform(text)
        assert result.transformed is False


class TestOptions:
    def test_preserve_blank_lines(self):
        text = "echo hi \\\n  --flag\n\necho bye \\\n  --other"
        result = transform(text, aggressiveness=Aggressiveness.HIGH, preserve_blank_lines=True)
        assert "\n\n" in result.text


class TestBoxDrawing:
    def test_strips_pipes_from_tabular_output(self):
        text = "│ git status │\n│ git log    │"
        assert "│" not in transform(text, aggressiveness=Aggressiveness.HIGH).text

    def test_keep_box_drawing_preserves_characters(self):
        assert "│" in transform("│ content │", remove_box_drawing=False).text


class TestPathWithSpaces:
    @pytest.mark.parametrize("path", [
        "/Users/me/My Documents/file.txt",
        "~/My Folder/file.txt",
        "./local dir/notes.md",
    ])
    def test_wraps_path_in_quotes(self, path):
        assert transform(path).text == f'"{path}"'

    @pytest.mark.parametrize("text", [
        '"/Users/me/My Docs/file.txt"',
        "ls -la /some/dir",
    ])
    def test_leaves_non_paths_alone(self, text):
        assert transform(text).transformed is False


class TestSmartPromptStripping:
    @pytest.mark.parametrize("text", [
        "# Overview\n# Usage notes\n# Final thoughts",
        "# First idea here.\n# Second idea there.\n# Third idea too.",
    ])
    def test_leaves_prose_with_prompt_chars_alone(self, text):
        assert transform(text).transformed is False


class TestIndependentCommandsGuard:
    def test_sequential_commands_not_glued(self):
        assert transform("cd foo\nls -la\necho done").transformed is False
