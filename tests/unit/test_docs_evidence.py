"""Unit tests for the docs evidence extractor."""

from __future__ import annotations

from rkp.core.types import SourceAuthority
from rkp.indexer.extractors.docs_evidence import extract_docs_evidence


class TestExtractDocsEvidence:
    def test_extracts_commands_from_code_blocks(self, tmp_path):
        """Extract operational commands from fenced code blocks."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# My App\n\n## Getting Started\n\n```bash\npip install -e .\npytest tests/\n```\n"
        )

        result = extract_docs_evidence(tmp_path)
        assert result.files_scanned == 1
        commands = [c.content for c in result.commands]
        assert "pip install -e ." in commands
        assert "pytest tests/" in commands

    def test_shell_prompt_stripped(self, tmp_path):
        """Leading $ is stripped from commands."""
        readme = tmp_path / "README.md"
        readme.write_text("## Setup\n\n```bash\n$ npm install\n```\n")

        result = extract_docs_evidence(tmp_path)
        commands = [c.content for c in result.commands]
        assert "npm install" in commands

    def test_skips_non_operational_content(self, tmp_path):
        """Non-operational content (explanatory text) is not extracted."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# My App\n\nThis is a great app.\n\n```python\nx = 1 + 2\nprint(x)\n```\n"
        )

        result = extract_docs_evidence(tmp_path)
        # Python code blocks should not be extracted as commands
        commands = [c.content for c in result.commands]
        assert "x = 1 + 2" not in commands

    def test_extracts_prerequisites_from_prose(self, tmp_path):
        """Runtime requirements mentioned in prose are extracted."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# My App\n\n## Prerequisites\n\nRequires Python 3.12+\n\nRequires Node.js >= 18\n"
        )

        result = extract_docs_evidence(tmp_path)
        prereq_contents = [p.content for p in result.prerequisites]
        assert any("Python 3.12" in c for c in prereq_contents)

    def test_no_readme(self, tmp_path):
        """Handle missing README gracefully."""
        result = extract_docs_evidence(tmp_path)
        assert result.files_scanned == 0
        assert len(result.commands) == 0

    def test_empty_readme(self, tmp_path):
        """Handle README with no code blocks."""
        readme = tmp_path / "README.md"
        readme.write_text("# My App\n\nJust some text.")

        result = extract_docs_evidence(tmp_path)
        assert result.files_scanned == 1
        assert len(result.commands) == 0

    def test_docs_directory_scanned(self, tmp_path):
        """Files in docs/ directory are also scanned."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "setup.md").write_text("## Setup\n\n```bash\nmake dev\n```\n")

        result = extract_docs_evidence(tmp_path)
        assert result.files_scanned >= 1
        commands = [c.content for c in result.commands]
        assert "make dev" in commands

    def test_commands_have_checked_in_docs_authority(self, tmp_path):
        """Commands from docs have source_authority = checked-in-docs."""
        readme = tmp_path / "README.md"
        readme.write_text("## Dev\n\n```bash\nnpm install\n```\n")

        result = extract_docs_evidence(tmp_path)
        for cmd in result.commands:
            assert cmd.source_authority == SourceAuthority.CHECKED_IN_DOCS

    def test_confidence_higher_under_operational_heading(self, tmp_path):
        """Commands under known operational headings get higher confidence."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "## Getting Started\n\n"
            "```bash\n"
            "pip install -e .\n"
            "```\n\n"
            "## Notes\n\n"
            "```bash\n"
            "docker build .\n"
            "```\n"
        )

        result = extract_docs_evidence(tmp_path)
        getting_started_cmd = next(c for c in result.commands if "pip install" in c.content)
        notes_cmd = next(c for c in result.commands if "docker build" in c.content)
        assert getting_started_cmd.confidence >= notes_cmd.confidence

    def test_multiple_code_block_languages(self, tmp_path):
        """Handle bash, shell, sh, and untagged code blocks."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "## Commands\n\n"
            "```bash\n"
            "npm install\n"
            "```\n\n"
            "```shell\n"
            "npm test\n"
            "```\n\n"
            "```sh\n"
            "npm run build\n"
            "```\n\n"
            "```\n"
            "npm run lint\n"
            "```\n"
        )

        result = extract_docs_evidence(tmp_path)
        commands = [c.content for c in result.commands]
        assert "npm install" in commands
        # "npm test" starts with a valid prefix
        assert any("npm" in cmd for cmd in commands)

    def test_inline_comments_are_stripped_and_deduplicated(self, tmp_path):
        """Trailing inline comments do not create duplicate commands."""
        readme = tmp_path / "README.md"
        readme.write_text("## Testing\n\n```bash\nnox -s test  # full suite\nnox -s test\n```\n")

        result = extract_docs_evidence(tmp_path)
        commands = [c.content for c in result.commands]
        assert commands == ["nox -s test"]

    def test_excluded_docs_directory_is_skipped(self, tmp_path):
        """Repo config exclusions can suppress docs/ during extraction."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "setup.md").write_text("## Setup\n\n```bash\nmake dev\n```\n", encoding="utf-8")

        result = extract_docs_evidence(tmp_path, excluded_dirs=("docs",))

        assert result.files_scanned == 0
        assert result.commands == ()
