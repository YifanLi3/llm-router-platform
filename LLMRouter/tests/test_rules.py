"""Tests for the AST-based safe rule evaluator."""

import pytest

from app.core.rules import RuleRuntimeError, RuleSyntaxError, safe_eval

CTX = {"query_type": "coding", "token_count": 120, "user_tier": "premium"}


class TestHappyPath:
    def test_equality_true(self):
        assert safe_eval("query_type == 'coding'", CTX) is True

    def test_equality_false(self):
        assert safe_eval("query_type == 'general'", CTX) is False

    def test_and(self):
        assert safe_eval("query_type == 'coding' and token_count > 100", CTX) is True

    def test_or(self):
        assert safe_eval("query_type == 'general' or token_count > 100", CTX) is True

    def test_in(self):
        assert safe_eval("user_tier in ['premium', 'enterprise']", CTX) is True

    def test_not_in(self):
        assert safe_eval("user_tier not in ['free']", CTX) is True

    def test_not(self):
        assert safe_eval("not (user_tier == 'free')", CTX) is True

    def test_chained_comparison(self):
        # 10 < 120 < 200
        assert safe_eval("10 < token_count < 200", CTX) is True


class TestRejectsMaliciousInput:
    @pytest.mark.parametrize(
        "expr",
        [
            "__import__('os').system('rm -rf /')",   # Call + Attribute
            "open('/etc/passwd').read()",            # Call
            "os.system('ls')",                       # Attribute
            "lambda: 1",                             # Lambda
            "[1, 2].append(3)",                      # Attribute + Call
            "1 + 1",                                 # BinOp (arithmetic)
            "token_count * 2 > 100",                 # BinOp
        ],
    )
    def test_disallowed_syntax(self, expr):
        with pytest.raises(RuleSyntaxError):
            safe_eval(expr, CTX)


class TestRuntimeErrors:
    def test_unknown_variable(self):
        with pytest.raises(RuleRuntimeError):
            safe_eval("nonexistent == 1", CTX)

    def test_broken_syntax(self):
        with pytest.raises(RuleSyntaxError):
            safe_eval("query_type ==", CTX)


class TestIntegrationWithConfigRules:
    """Sanity: every rule in config.yaml should at least parse & evaluate."""

    def test_all_config_rules_evaluate(self):
        from app.core.config import get_config

        cfg = get_config()
        ctx = {"query_type": "coding", "token_count": 50, "user_tier": "free"}
        for rule in cfg.router.routing_rules:
            # We don't care about True/False -- we care that it doesn't blow up.
            result = safe_eval(rule.condition, ctx)
            assert isinstance(result, bool), f"rule {rule.name!r} returned {result!r}"