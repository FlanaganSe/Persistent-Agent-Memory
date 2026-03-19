"""Tests for secret detection (M10)."""

from __future__ import annotations

from rkp.core.security import redact_secrets, scan_for_secrets


class TestScanForSecrets:
    """Secret pattern detection with redaction."""

    # -- Provider-specific patterns --

    def test_aws_access_key(self) -> None:
        content = "aws_key = AKIAIOSFODNN7EXAMPLE"
        findings = scan_for_secrets(content)
        assert len(findings) >= 1
        assert any("AWS" in f.pattern_type for f in findings)

    def test_github_pat(self) -> None:
        content = "token = ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        findings = scan_for_secrets(content)
        assert any("GitHub personal" in f.pattern_type for f in findings)

    def test_github_oauth_token(self) -> None:
        content = "oauth = gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        findings = scan_for_secrets(content)
        assert any("GitHub OAuth" in f.pattern_type for f in findings)

    def test_github_fine_grained_pat(self) -> None:
        value = "github_pat_" + "A" * 82
        content = f"token = {value}"
        findings = scan_for_secrets(content)
        assert any("GitHub fine-grained" in f.pattern_type for f in findings)

    def test_openai_key(self) -> None:
        content = "key = sk-" + "A" * 48
        findings = scan_for_secrets(content)
        assert any("OpenAI" in f.pattern_type or "API" in f.pattern_type for f in findings)

    def test_anthropic_key(self) -> None:
        content = "key = sk-ant-" + "A" * 90
        findings = scan_for_secrets(content)
        assert any("Anthropic" in f.pattern_type for f in findings)

    def test_slack_bot_token(self) -> None:
        content = "token = xoxb-" + "1234567890-1234567890123-ABCDEFGHIJKLMNOPQRSTUVwx"
        findings = scan_for_secrets(content)
        assert any("Slack bot" in f.pattern_type for f in findings)

    def test_slack_user_token(self) -> None:
        content = "token = xoxp-" + "1234567890-1234567890123-ABCDEFGHIJKLMNOPQRSTUVwx"
        findings = scan_for_secrets(content)
        assert any("Slack user" in f.pattern_type for f in findings)

    # -- Connection strings --

    def test_postgres_connection_string(self) -> None:
        content = "DATABASE_URL=postgres://user:pass@host:5432/db"
        findings = scan_for_secrets(content)
        assert any("Database" in f.pattern_type for f in findings)

    def test_mysql_connection_string(self) -> None:
        content = "db = mysql://root:secret@localhost/mydb"
        findings = scan_for_secrets(content)
        assert any("Database" in f.pattern_type for f in findings)

    def test_mongodb_connection_string(self) -> None:
        content = "MONGO_URI=mongodb://admin:password123@cluster0.mongodb.net/test"
        findings = scan_for_secrets(content)
        assert any("Database" in f.pattern_type for f in findings)

    def test_redis_connection_string(self) -> None:
        content = "REDIS_URL=redis://:mysecret@redis.host:6379/0"
        findings = scan_for_secrets(content)
        assert any("Redis" in f.pattern_type for f in findings)

    # -- Private keys --

    def test_private_key_header(self) -> None:
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."
        findings = scan_for_secrets(content)
        assert any("Private key" in f.pattern_type for f in findings)

    def test_ec_private_key(self) -> None:
        content = "-----BEGIN EC PRIVATE KEY-----"
        findings = scan_for_secrets(content)
        assert any("Private key" in f.pattern_type for f in findings)

    def test_ssh_private_key(self) -> None:
        content = "-----BEGIN OPENSSH PRIVATE KEY-----"
        findings = scan_for_secrets(content)
        assert any("SSH private key" in f.pattern_type for f in findings)

    # -- Generic key/token patterns --

    def test_api_key_assignment(self) -> None:
        content = "API_KEY=sk_live_abcdef1234567890abcd"
        findings = scan_for_secrets(content)
        assert len(findings) >= 1

    def test_secret_key_assignment(self) -> None:
        content = "SECRET_KEY='ABCDEFghijklmnopqrst12345'"
        findings = scan_for_secrets(content)
        assert len(findings) >= 1

    def test_auth_token_assignment(self) -> None:
        content = 'auth_token = "aBcDeFgHiJkLmNoPqRsT1234"'
        findings = scan_for_secrets(content)
        assert len(findings) >= 1

    # -- Entropy-based detection --

    def test_high_entropy_password(self) -> None:
        # High-entropy string in assignment context.
        content = 'password = "xK9#mQ2$vL5@nR8^tY3!pW6"'
        findings = scan_for_secrets(content)
        assert len(findings) >= 1

    # -- No false positives --

    def test_normal_variable_names(self) -> None:
        content = """
def process_data():
    system_config = get_config()
    token_count = len(tokens)
    key_name = "username"
    return system_config
"""
        findings = scan_for_secrets(content)
        assert findings == []

    def test_git_commit_hash(self) -> None:
        content = "commit = a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        findings = scan_for_secrets(content)
        # Entropy check should exclude git hashes.
        hash_findings = [f for f in findings if "entropy" in f.pattern_type.lower()]
        assert hash_findings == []

    def test_uuid(self) -> None:
        content = 'id = "550e8400-e29b-41d4-a716-446655440000"'
        findings = scan_for_secrets(content)
        uuid_findings = [f for f in findings if "entropy" in f.pattern_type.lower()]
        assert uuid_findings == []

    def test_empty_content(self) -> None:
        assert scan_for_secrets("") == []

    def test_short_values_not_flagged(self) -> None:
        """Values shorter than 20 chars should not be flagged by generic patterns."""
        content = "api_key = abc123"
        findings = scan_for_secrets(content)
        assert findings == []

    # -- Redaction context --

    def test_redacted_context_masks_value(self) -> None:
        content = "API_KEY=AKIAIOSFODNN7EXAMPLE"
        findings = scan_for_secrets(content)
        assert len(findings) >= 1
        for finding in findings:
            assert "REDACTED" in finding.redacted_context

    def test_line_number_accuracy(self) -> None:
        content = "line 1\nline 2\nAPI_KEY=AKIAIOSFODNN7EXAMPLE\nline 4"
        findings = scan_for_secrets(content)
        aws_finding = next(f for f in findings if "AWS" in f.pattern_type)
        assert aws_finding.line_number == 3


class TestRedactSecrets:
    def test_redacts_secret_value(self) -> None:
        content = "API_KEY=AKIAIOSFODNN7EXAMPLE"
        findings = scan_for_secrets(content)
        redacted = redact_secrets(content, findings)
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted
        assert "REDACTED" in redacted

    def test_preserves_non_secret_content(self) -> None:
        content = "name = test\nAPI_KEY=AKIAIOSFODNN7EXAMPLE\nversion = 1.0"
        findings = scan_for_secrets(content)
        redacted = redact_secrets(content, findings)
        assert "name = test" in redacted
        assert "version = 1.0" in redacted
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted

    def test_no_findings_no_change(self) -> None:
        content = "normal text here"
        redacted = redact_secrets(content, [])
        assert redacted == content

    def test_multiple_secrets_redacted(self) -> None:
        content = "KEY1=AKIAIOSFODNN7EXAMPLE\nKEY2=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        findings = scan_for_secrets(content)
        redacted = redact_secrets(content, findings)
        assert "AKIAIOSFODNN7EXAMPLE" not in redacted
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in redacted
