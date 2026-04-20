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
    def test_strips_leading_and_trailing_pipes(self):
        text = "│ git status │\n│ git log    │"
        result = transform(text, aggressiveness=Aggressiveness.HIGH)
        assert "│" not in result.text

    def test_keep_box_drawing_flag(self):
        text = "│ content │"
        result = transform(text, remove_box_drawing=False)
        assert "│" in result.text


class TestPathWithSpaces:
    def test_quotes_absolute_path_with_spaces(self):
        assert transform("/Users/me/My Documents/file.txt").text == '"/Users/me/My Documents/file.txt"'

    def test_quotes_home_path_with_spaces(self):
        assert transform("~/My Folder/file.txt").text == '"~/My Folder/file.txt"'

    def test_does_not_quote_urls(self):
        result = transform("https://example.com/a b")
        assert not (result.text.startswith('"') and result.text.endswith('"'))

    def test_does_not_quote_already_quoted(self):
        assert transform('"/Users/me/My Docs/file.txt"').transformed is False

    def test_does_not_quote_commands_with_flags(self):
        assert transform("ls -la /some/dir").transformed is False


class TestPromptStrippingStrictness:
    def test_strips_real_shell_prompts(self):
        result = transform("$ echo hi\n$ ls -la")
        assert "$" not in result.text

    def test_does_not_strip_markdown_headings(self):
        text = "# Overview\n# Usage notes\n# Final thoughts"
        assert transform(text).transformed is False

    def test_does_not_strip_prose_majority(self):
        text = "# First idea here.\n# Second idea there.\nplain trailing line"
        assert "# First" in transform(text).text


class TestIndependentCommandsGuard:
    def test_three_independent_commands_not_flattened(self):
        text = "cd foo\nls -la\necho done"
        result = transform(text)
        assert "\n" in result.text or result.transformed is False

    def test_indented_continuations_still_flatten(self):
        text = "kubectl get pods\n  --namespace prod\n  -o wide\n  --selector app=web"
        result = transform(text)
        assert result.text == "kubectl get pods --namespace prod -o wide --selector app=web"
