"""Regression checks for Toga startup UI composition."""

import ast
from pathlib import Path


APP_SOURCE = Path(__file__).parents[1] / "src/worktime_tracker/app.py"


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def test_startup_passes_all_tabs_to_option_container_constructor():
    tree = ast.parse(APP_SOURCE.read_text(encoding="utf-8"))
    option_container = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and dotted_name(node.func) == "toga.OptionContainer"
    )
    content = next(
        keyword.value
        for keyword in option_container.keywords
        if keyword.arg == "content"
    )
    assert isinstance(content, ast.List)
    labels = [ast.literal_eval(item.elts[0]) for item in content.elts]
    assert labels == ["首頁", "紀錄", "日曆", "分析", "設定"]


def test_startup_never_assigns_option_container_content_property():
    tree = ast.parse(APP_SOURCE.read_text(encoding="utf-8"))
    invalid_targets = [
        target
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "tabs"
        and target.attr == "content"
    ]
    assert invalid_targets == []
