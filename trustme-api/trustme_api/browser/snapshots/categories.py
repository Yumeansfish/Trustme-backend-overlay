import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from trustme_api.browser.snapshots.models import (
    CompiledCategoryMatcher,
    CompiledCategoryRule,
    CompiledCategoryTermRule,
    UNCATEGORIZED_CATEGORY_NAME,
)


def compile_category_rules(rules: Sequence[Any]) -> CompiledCategoryMatcher:
    parsed_rules = []
    for rule in rules:
        if not isinstance(rule, list) or len(rule) != 2:
            continue
        category_name, definition = rule
        if not isinstance(definition, dict):
            continue
        if definition.get("type") != "regex":
            continue

        category = normalize_category_name(category_name)
        depth = len(category)
        ignore_case = bool(definition.get("ignore_case"))
        regex = _compile_regex(definition)
        exact_apps = _normalize_match_terms(definition.get("exact_apps"), ignore_case=ignore_case)
        domains = _normalize_match_terms(definition.get("domains"), ignore_case=ignore_case)
        aliases = _normalize_match_terms(definition.get("aliases"), ignore_case=ignore_case)
        title_keywords = _normalize_match_terms(
            definition.get("title_keywords"),
            ignore_case=ignore_case,
        )

        if regex is None and not (exact_apps or domains or aliases or title_keywords):
            continue

        parsed_rules.append(
            {
                "category": category,
                "depth": depth,
                "ignore_case": ignore_case,
                "regex": regex,
                "exact_apps": exact_apps,
                "domains": domains,
                "aliases": aliases,
                "title_keywords": title_keywords,
            }
        )

    ordered_rules = sorted(parsed_rules, key=lambda rule: rule["depth"], reverse=True)

    exact_apps_case_sensitive: Dict[str, List[str]] = {}
    exact_apps_casefolded: Dict[str, List[str]] = {}
    domains_case_sensitive: Dict[str, Tuple[int, List[str]]] = {}
    domains_casefolded: Dict[str, Tuple[int, List[str]]] = {}
    alias_rules: List[CompiledCategoryTermRule] = []
    title_rules: List[CompiledCategoryTermRule] = []
    regex_rules: List[CompiledCategoryRule] = []

    for precedence, rule in enumerate(ordered_rules):
        for app in rule["exact_apps"]:
            target_map = (
                exact_apps_casefolded if rule["ignore_case"] else exact_apps_case_sensitive
            )
            target_map.setdefault(app, list(rule["category"]))

        for domain in rule["domains"]:
            target_map = domains_casefolded if rule["ignore_case"] else domains_case_sensitive
            target_map.setdefault(domain, (precedence, list(rule["category"])))

        if rule["aliases"]:
            alias_rules.append(
                CompiledCategoryTermRule(
                    category=list(rule["category"]),
                    terms=rule["aliases"],
                    depth=rule["depth"],
                    ignore_case=rule["ignore_case"],
                )
            )

        if rule["title_keywords"]:
            title_rules.append(
                CompiledCategoryTermRule(
                    category=list(rule["category"]),
                    terms=rule["title_keywords"],
                    depth=rule["depth"],
                    ignore_case=rule["ignore_case"],
                )
            )

        if rule["regex"] is not None:
            regex_rules.append(
                CompiledCategoryRule(
                    category=list(rule["category"]),
                    regex=rule["regex"],
                    depth=rule["depth"],
                )
            )

    return CompiledCategoryMatcher(
        exact_apps_case_sensitive=exact_apps_case_sensitive,
        exact_apps_casefolded=exact_apps_casefolded,
        domains_case_sensitive=domains_case_sensitive,
        domains_casefolded=domains_casefolded,
        alias_rules=tuple(alias_rules),
        title_rules=tuple(title_rules),
        regex_rules=tuple(regex_rules),
    )


def normalize_category_name(category: Any) -> List[str]:
    if isinstance(category, list) and category:
        return [str(part) for part in category]
    if isinstance(category, str) and category.strip():
        return [category.strip()]
    return list(UNCATEGORIZED_CATEGORY_NAME)


def resolve_category_for_data(
    data: Dict[str, Any],
    compiled_rules: CompiledCategoryMatcher,
    category_cache: Optional[Dict[Tuple[str, str, str], List[str]]] = None,
) -> List[str]:
    manual_category = manual_away_category_from_data(data)
    if manual_category is not None:
        return manual_category

    app = data.get("app").strip() if isinstance(data.get("app"), str) else ""
    title = data.get("title").strip() if isinstance(data.get("title"), str) else ""
    domain = domain_from_data(data)
    cache_key = (app, title, domain.casefold())
    if category_cache is not None:
        cached = category_cache.get(cache_key)
        if cached is not None:
            return list(cached)

    resolved = _resolve_category_for_texts(
        app=app,
        title=title,
        domain=domain,
        compiled_rules=compiled_rules,
    )
    if category_cache is not None:
        category_cache[cache_key] = list(resolved)
    return resolved


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


def domain_from_data(data: Dict[str, Any]) -> str:
    explicit_domain = data.get("$domain")
    if isinstance(explicit_domain, str) and explicit_domain.strip():
        return explicit_domain.strip()

    raw_url = data.get("url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        return ""

    hostname = urlparse(raw_url.strip()).hostname
    return hostname or ""


def _resolve_category_for_texts(
    *,
    app: str,
    title: str,
    domain: str,
    compiled_rules: CompiledCategoryMatcher,
) -> List[str]:
    exact_app_match = _lookup_exact_app(app, compiled_rules)
    if exact_app_match is not None:
        return exact_app_match

    domain_match = _lookup_domain(domain, compiled_rules)
    if domain_match is not None:
        return domain_match

    alias_match = _match_term_rules((app, title), compiled_rules.alias_rules)
    if alias_match is not None:
        return alias_match

    title_match = _match_term_rules((title,), compiled_rules.title_rules)
    if title_match is not None:
        return title_match

    for rule in compiled_rules.regex_rules:
        if rule.regex.search(app) or rule.regex.search(title):
            return list(rule.category)

    return list(UNCATEGORIZED_CATEGORY_NAME)


def _compile_regex(definition: Dict[str, Any]):
    regex = definition.get("regex")
    if not isinstance(regex, str) or not regex:
        return None

    flags = re.MULTILINE
    if definition.get("ignore_case"):
        flags |= re.IGNORECASE

    try:
        return re.compile(regex, flags)
    except re.error:
        return None


def _normalize_match_terms(values: Any, *, ignore_case: bool) -> Tuple[str, ...]:
    if not isinstance(values, list):
        return ()

    results = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        trimmed = value.strip()
        if not trimmed:
            continue
        normalized = trimmed.casefold() if ignore_case else trimmed
        if normalized in seen:
            continue
        results.append(normalized)
        seen.add(normalized)
    return tuple(results)


def _lookup_exact_app(app: str, compiled_rules: CompiledCategoryMatcher) -> Optional[List[str]]:
    if not app:
        return None
    if app in compiled_rules.exact_apps_case_sensitive:
        return list(compiled_rules.exact_apps_case_sensitive[app])

    exact = compiled_rules.exact_apps_casefolded.get(app.casefold())
    return list(exact) if exact is not None else None


def _lookup_domain(domain: str, compiled_rules: CompiledCategoryMatcher) -> Optional[List[str]]:
    if not domain:
        return None

    best_match: Optional[Tuple[int, List[str]]] = None
    for candidate in _iter_domain_candidates(domain):
        entry = compiled_rules.domains_case_sensitive.get(candidate)
        if entry is not None and (best_match is None or entry[0] < best_match[0]):
            best_match = entry

    for candidate in _iter_domain_candidates(domain.casefold()):
        entry = compiled_rules.domains_casefolded.get(candidate)
        if entry is not None and (best_match is None or entry[0] < best_match[0]):
            best_match = entry

    return list(best_match[1]) if best_match is not None else None


def _iter_domain_candidates(domain: str) -> Tuple[str, ...]:
    labels = [label for label in domain.split(".") if label]
    if len(labels) < 2:
        return (domain,) if domain else ()
    return tuple(".".join(labels[index:]) for index in range(len(labels) - 1))


def _match_term_rules(
    texts: Tuple[str, ...],
    rules: Sequence[CompiledCategoryTermRule],
) -> Optional[List[str]]:
    raw_texts = tuple(text for text in texts if text)
    folded_texts = tuple(text.casefold() for text in raw_texts)

    for rule in rules:
        haystacks = folded_texts if rule.ignore_case else raw_texts
        for text in haystacks:
            for term in rule.terms:
                if _contains_boundary_term(text, term):
                    return list(rule.category)
    return None


def _contains_boundary_term(text: str, term: str) -> bool:
    start = 0
    while True:
        index = text.find(term, start)
        if index == -1:
            return False
        end = index + len(term)
        if (index == 0 or not text[index - 1].isalnum()) and (
            end == len(text) or not text[end].isalnum()
        ):
            return True
        start = index + 1
