"""AST-based structural style checks for staged Python files.

This module enforces the repo owner's structural style hates: underscore-prefixed names, star unpacking,
pointless classes, and oversized modules. It models the same rules it enforces: few functions, few classes,
no star unpacking.

Use this file ONLY for rules that ruff, pylint, and pyright cannot express — AST-structural patterns.
Plain style, naming, typing, and complexity belong in pyproject.toml, not here. Keep it short: a long
preferences file is a smell. The functions below are working examples to copy.

Adding a check: write `name(path, tree) -> list[str]` returning "path:line: message" strings, then call
it from `preferences_violations`. Skeleton:

    def no_global_statement(path: str, tree: ast.Module) -> list[str]:
        return [
            f"{path}:{node.lineno}: 'global' statement; pass values explicitly"
            for node in ast.walk(tree)
            if isinstance(node, ast.Global)
        ]
"""

from __future__ import annotations

import ast

MAX_FUNCTIONS_PER_FILE = 5


def underscore_violations(path: str, tree: ast.Module) -> list[str]:
    """Flag function, argument, and assigned names that start with an underscore."""
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found = (node.name, node.lineno)
        elif isinstance(node, ast.arg):
            found = (node.arg, node.lineno)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            found = (node.id, node.lineno)
        else:
            continue
        if found[0].startswith("_") and not found[0].endswith("__"):
            problems.append(f"{path}:{found[1]}: name '{found[0]}' starts with underscore")
    return problems


def star_violations(path: str, tree: ast.Module) -> list[str]:
    """Flag star and double-star unpacking in calls, assignments, and signatures."""
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Starred):
            problems.append(f"{path}:{node.lineno}: star unpacking; pass explicit values")
        elif isinstance(node, ast.keyword) and node.arg is None:
            problems.append(f"{path}:{node.lineno}: double-star unpacking; pass explicit arguments")
        elif isinstance(node, ast.arguments) and (node.vararg or node.kwarg):
            problems.append(f"{path}: signature uses *args or **kwargs; declare explicit parameters")
    return problems


def class_violations(path: str, tree: ast.Module) -> list[str]:
    """Flag plain classes that should be module functions or a dataclass."""
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.bases or node.keywords or node.decorator_list:
            continue
        methods = [item for item in node.body if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)]
        if len(methods) <= 1:
            problems.append(
                f"{path}:{node.lineno}: class '{node.name}' has no base, decorator, or behavior; "
                "use module functions or a dataclass"
            )
    return problems


def preferences_violations(path: str, source: str, limit: int) -> list[str]:
    """Run every structural check on one Python file; limit 0 skips the function count."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"{path}: could not parse: {error.msg} (line {error.lineno})"]
    problems = underscore_violations(path, tree)
    problems.extend(star_violations(path, tree))
    problems.extend(class_violations(path, tree))
    top = [node for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]
    if limit and len(top) > limit:
        problems.append(f"{path}: {len(top)} top-level functions exceeds limit {limit}; split the module")
    return problems
