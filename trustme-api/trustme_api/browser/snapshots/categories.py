import re
from typing import Any, Dict, List, Optional, Sequence

from .summary_snapshot_models import CompiledCategoryRule, UNCATEGORIZED_CATEGORY_NAME


def compile_category_rules(rules: Sequence[Any]) -> List[CompiledCategoryRule]:
    compiled_rules: List[CompiledCategoryRule] = []
    for rule in rules:
        if not isinstance(rule, list) or len(rule) != 2:
            continue
        category_name, definition = rule
        if not isinstance(definition, dict):
            continue
        if definition.get("type") != "regex" or not definition.get("regex"):
            continue

        flags = re.MULTILINE
        if definition.get("ignore_case"):
            flags |= re.IGNORECASE

        try:
            compiled_rules.append(
                CompiledCategoryRule(
                    category=normalize_category_name(category_name),
                    regex=re.compile(str(definition["regex"]), flags),
                )
            )
        except re.error:
            continue
    return compiled_rules


def normalize_category_name(category: Any) -> List[str]:
    if isinstance(category, list) and category:
        return [str(part) for part in category]
    if isinstance(category, str) and category.strip():
        return [category.strip()]
    return list(UNCATEGORIZED_CATEGORY_NAME)


def resolve_category_for_data(
    data: Dict[str, Any], compiled_rules: Sequence[CompiledCategoryRule]
) -> List[str]:
    manual_category = manual_away_category_from_data(data)
    if manual_category is not None:
        return manual_category

    app = data.get("app") if isinstance(data.get("app"), str) else ""
    title = data.get("title") if isinstance(data.get("title"), str) else ""

    matches = [
        rule.category
        for rule in compiled_rules
        if rule.regex.search(app) or rule.regex.search(title)
    ]
    if not matches:
        return list(UNCATEGORIZED_CATEGORY_NAME)
    return max(matches, key=len)


def manual_away_category_from_data(data: Dict[str, Any]) -> Optional[List[str]]:
    explicit_category = data.get("$category")
    if isinstance(explicit_category, list) and explicit_category:
        return [str(part) for part in explicit_category]
    if isinstance(explicit_category, str) and explicit_category.strip():
        return [explicit_category.strip()]

    is_manual_away = data.get("$manual_away") is True or (
        isinstance(data.get("label"), str) and isinstance(data.get("running"), bool)
    )
    if not is_manual_away:
        return None

    label = data.get("label").strip() if isinstance(data.get("label"), str) else ""
    return [label] if label else list(UNCATEGORIZED_CATEGORY_NAME)
