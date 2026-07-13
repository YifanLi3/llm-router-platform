"""Safe boolean expression evaluator for routing rules.

Routing rules in config.yaml look like:
    condition: "query_type == 'coding' and token_count > 80"

We must NEVER pass that string to Python's `eval()` -- a malicious rule
like `__import__('os').system('rm -rf /')` would then run.
Instead we parse the expression to an AST and manually walk it, refusing
any node whose type is not on the whitelist below.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from typing import Any, Mapping

# Only these AST node types are permitted anywhere in the tree.
# In particular: NO Call, NO Attribute, NO BinOp, NO Import, NO Lambda.
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not,
    ast.Compare,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn,
    ast.Name, ast.Load,
    ast.Constant,
    ast.List, ast.Tuple,
)

class RuleSyntaxError(ValueError):
    """Rule contains disallowed syntax (rejected at parse time)."""

class RuleRuntimeError(RuntimeError):
    """Rule parsed fine but failed at evaluation (e.g. unknown variable)."""

@lru_cache(maxsize=256)
def _parse(expr: str) -> ast.Expression:
    """Parse `expr` and validate every node against the whitelist.
    Cached because we typically evaluate the same handful of rules over
    and over across requests.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise RuleSyntaxError(f"invalid syntax in rule: {expr!r}") from e
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise RuleSyntaxError(
                f"disallowed AST node {type(node).__name__} in rule: {expr!r}"
            )
    return tree
def _eval(node: ast.AST, ctx: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, ctx)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise RuleRuntimeError(f"unknown variable {node.id!r} in rule")
        return ctx[node.id]
    if isinstance(node, ast.List):
        return [_eval(e, ctx) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval(e, ctx) for e in node.elts)
    if isinstance(node, ast.UnaryOp):
        # Whitelist guarantees op is ast.Not.
        return not _eval(node.operand, ctx)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not _eval(value, ctx):
                    return False
            return True
        # ast.Or
        for value in node.values:
            if _eval(value, ctx):
                return True
        return False
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, ctx)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.In):
                ok = left in right
            elif isinstance(op, ast.NotIn):
                ok = left not in right
            else:
                raise RuleSyntaxError(f"unsupported comparator {type(op).__name__}")
            if not ok:
                return False
            left = right
        return True
    raise RuleSyntaxError(f"unhandled node {type(node).__name__}")
def safe_eval(expr: str, context: Mapping[str, Any]) -> bool:
    """Evaluate `expr` against `context`, returning a boolean.
    Raises RuleSyntaxError if `expr` contains disallowed syntax.
    Raises RuleRuntimeError if `expr` references an undefined variable.
    """
    tree = _parse(expr)
    return bool(_eval(tree, context))
# ---------------------------------------------------------------------------
# Self-test: `uv run python -m app.core.rules`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ctx = {"query_type": "coding", "token_count": 120, "user_tier": "premium"}
    cases = [
        ("query_type == 'coding'",                                        True),
        ("query_type == 'coding' and token_count > 100",                  True),
        ("query_type == 'general' or token_count > 100",                  True),
        ("user_tier in ['premium', 'enterprise']",                        True),
        ("user_tier not in ['free']",                                     True),
        ("not (user_tier == 'free')",                                     True),
        ("token_count < 10",                                              False),
    ]
    print("[legal rules]")
    for expr, expected in cases:
        got = safe_eval(expr, ctx)
        mark = "OK " if got is expected else "BAD"
        print(f"  {mark} {expr!r:60s} -> {got}")
    print("\n[should be rejected]")
    evil = [
        "__import__('os').system('rm -rf /')",
        "open('/etc/passwd').read()",
        "1 + 1",
        "lambda: 1",
    ]
    for expr in evil:
        try:
            safe_eval(expr, ctx)
            print(f"  BAD  {expr!r} was ACCEPTED (should have rejected)")
        except (RuleSyntaxError, RuleRuntimeError) as e:
            print(f"  OK   {expr!r}\n         -> {type(e).__name__}: {e}")

