"""Tests for SecretLeakageRule (output guard) — 0.3.1 coverage."""

from __future__ import annotations

from neurosym.rules.output.secrets import _OVERLAP, SecretLeakageRule

# ── helpers ──────────────────────────────────────────────────────────────────

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GITHUB_PAT = "ghp_" + "A" * 36
GITHUB_FINE_GRAINED = "github_pat_" + "A" * 82
GOOGLE_KEY = "AIzaSy" + "A" * 33  # AIza + 35 chars matches the pattern
SLACK_TOKEN = "xoxb-1234567890-1234567890-abcdefghij"
STRIPE_LIVE = "sk_live_" + "A" * 24
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
BEARER = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.foobar1234567890ABCDEFGHIJ"
PRIVATE_KEY_HEADER = "-----BEGIN RSA PRIVATE KEY-----"


def _check(text: str):
    return SecretLeakageRule().check(text)


# ── positive detections ───────────────────────────────────────────────────────


def test_detects_aws_key():
    v = _check(f"The key is {AWS_KEY}, keep it safe.")
    assert v is not None
    violations = v if isinstance(v, list) else [v]
    assert any(m["kind"] == "aws_access_key_id" for hit in violations for m in hit.meta["matches"])


def test_detects_github_pat():
    v = _check(f"Token: {GITHUB_PAT}")
    assert v is not None


def test_detects_github_fine_grained():
    v = _check(GITHUB_FINE_GRAINED)
    assert v is not None


def test_detects_google_api_key():
    v = _check(f"key={GOOGLE_KEY}")
    assert v is not None


def test_detects_slack_token():
    v = _check(f"Slack bot token: {SLACK_TOKEN}")
    assert v is not None


def test_detects_stripe_live_key():
    v = _check(f"Use {STRIPE_LIVE} for payments.")
    assert v is not None


def test_detects_jwt():
    v = _check(f"Authorization header value: {JWT}")
    assert v is not None


def test_detects_bearer_token():
    v = _check(BEARER)
    assert v is not None


def test_detects_private_key_header():
    v = _check(f"{PRIVATE_KEY_HEADER}\nMIIEo...")
    assert v is not None


# ── negative (no false positives) ────────────────────────────────────────────


def test_no_false_positive_uuid():
    assert _check("Request id: 550e8400-e29b-41d4-a716-446655440000") is None


def test_no_false_positive_short_hex():
    assert _check("Commit hash: deadbeef12345678") is None


def test_no_false_positive_plain_text():
    assert _check("This response contains no secrets whatsoever.") is None


# ── StreamingRule protocol ────────────────────────────────────────────────────


def test_streaming_feed_detects_secret_in_single_chunk():
    rule = SecretLeakageRule()
    vs = rule.feed(f"Here is your key: {AWS_KEY}")
    assert len(vs) == 1


def test_streaming_feed_detects_across_chunk_boundary():
    """Secret split across two chunks must be caught via the overlap window."""
    rule = SecretLeakageRule()
    # AKIA split: first chunk has prefix, second has the rest
    half = len(AWS_KEY) // 2
    prefix, suffix = AWS_KEY[:half], AWS_KEY[half:]
    padding = "x" * (_OVERLAP + 10)  # push past the non-overlap zone safely
    rule.feed(padding + prefix)
    vs = rule.feed(suffix + " and more text")
    # If not caught in feed, finalize must catch it
    if not vs:
        vs = rule.finalize()
    assert len(vs) >= 1, "Secret split across chunks was not detected"


def test_streaming_no_double_report():
    """Same match must not be reported twice (once in feed, once in finalize)."""
    rule = SecretLeakageRule()
    vs_feed = rule.feed(AWS_KEY)
    vs_fin = rule.finalize()
    all_spans = [
        tuple(m["span"]) for vs in (vs_feed, vs_fin) for v in vs for m in v.meta["matches"]
    ]
    assert len(all_spans) == len(set(all_spans)), "Duplicate span reported"


def test_streaming_reset_clears_state():
    rule = SecretLeakageRule()
    rule.feed(f"secret: {AWS_KEY}")
    rule.reset()
    assert rule._buffer == ""
    assert rule._seen_spans == set()
    # After reset, same secret should be detected fresh
    vs = rule.feed(f"again: {AWS_KEY}")
    assert len(vs) == 1


def test_streaming_clean_stream_no_violations():
    rule = SecretLeakageRule()
    for chunk in ["Hello ", "world! ", "No secrets here."]:
        vs = rule.feed(chunk)
        assert vs == []
    assert rule.finalize() == []
