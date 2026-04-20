import pytest
from trimmix.detector import Aggressiveness, detect_command


class TestRejectsNonCommands:
    @pytest.mark.parametrize("text", [
        "ls -la",
        "",
        "- item one\n- item two\n- item three",
        "1. first\n2. second\n3. third",
        '{\n  "Version": "2012-10-17",\n  "Statement": []\n}',
        "import os\nclass Foo:\n    def bar(self):\n        pass",
        "Meeting notes:\nDiscuss the API design.\nReview pull requests.",
    ])
    def test_rejects(self, text):
        assert detect_command(text) is False


class TestDetectsCommands:
    @pytest.mark.parametrize("text", [
        "docker run -d \\\n  --name my-container \\\n  -p 8080:80 \\\n  nginx:latest",
        "curl -X POST \\\n  -H 'Authorization: Bearer token' \\\n  https://api.example.com",
        "kubectl get pods\n  --namespace production\n  -o wide",
        "$ echo hi\n$ ls -la",
        "cat file.txt\n| grep pattern",
        "mkdir foo\n&& cd foo",
        "git commit\n  -m 'fix bug'",
    ])
    def test_detects(self, text):
        assert detect_command(text) is True

    def test_high_aggressiveness_allows_loose_match(self):
        assert detect_command("npm\ninstall", aggressiveness=Aggressiveness.HIGH) is True

    def test_low_aggressiveness_requires_strong_signals(self):
        assert detect_command("echo hello\nworld", aggressiveness=Aggressiveness.LOW) is False
        assert detect_command("echo hi \\\n--flag", aggressiveness=Aggressiveness.LOW) is True
