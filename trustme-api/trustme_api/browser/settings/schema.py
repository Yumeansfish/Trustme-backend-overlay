import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


SETTINGS_SCHEMA_VERSION = 1
CURRENT_CATEGORIZATION_KNOWLEDGEBASE_VERSION = 3
UNCATEGORIZED_COLOR = "#e5e5ea"
SETTINGS_KEY_ALIASES = {
    "alwaysActivePattern": "always_active_pattern",
}
ALLOWED_START_OF_WEEK = {"Monday", "Sunday"}
ALLOWED_THEME = {"light", "dark", "auto"}
_MISSING = object()


CATEGORY_METADATA: Dict[str, Dict[str, Any]] = {
    "Code": {"score": 10},
    "Design": {"score": 8},
    "Writing": {"score": 7},
    "Research": {"score": 6},
    "Browsing": {"score": 0},
    "Messaging": {"score": 2},
    "Meetings": {"score": 2},
    "Email": {"score": 1},
    "Planning": {"score": 6},
    "Gaming": {"score": -8},
    "Video": {"score": -4},
    "Music": {"score": -2},
    "Shopping": {"score": -3},
    "Finance": {"score": 2},
    "System": {"score": 0},
    "Miscellaneous": {"score": 0},
}


CATEGORY_PRIORITY: Dict[str, int] = {
    "Email": 120,
    "Meetings": 110,
    "Messaging": 100,
    "Code": 95,
    "Design": 90,
    "Writing": 85,
    "Research": 80,
    "Planning": 75,
    "Finance": 70,
    "Shopping": 65,
    "Gaming": 60,
    "Video": 55,
    "Music": 50,
    "System": 10,
    "Browsing": 0,
    "Miscellaneous": -10,
}


def _escape_regex_literal(value: str) -> str:
    return re.escape(value)


def _normalize_terms(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []

    results: List[str] = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        trimmed = value.strip()
        if not trimmed or trimmed in seen:
            continue
        results.append(trimmed)
        seen.add(trimmed)
    return results


def _build_boundary_pattern(values: List[str]) -> List[str]:
    return [
        rf"(?:^|[^A-Za-z0-9]){_escape_regex_literal(value).replace(r'\ ', r'\\s+')}(?:$|[^A-Za-z0-9])"
        for value in values
    ]


def _build_domain_pattern(values: List[str]) -> List[str]:
    return [
        rf"(?:^|[^A-Za-z0-9]){_escape_regex_literal(value.lower())}(?:$|[^A-Za-z0-9])"
        for value in values
    ]


def _build_knowledgebase_regex(category: Dict[str, Any]) -> str | None:
    exact_apps = _normalize_terms(category.get("exact_apps"))
    aliases = _normalize_terms(category.get("aliases"))
    domains = _normalize_terms(category.get("domains"))
    title_keywords = _normalize_terms(category.get("title_keywords"))

    patterns = [
        *_build_boundary_pattern(exact_apps),
        *_build_boundary_pattern(aliases),
        *_build_domain_pattern(domains),
        *_build_boundary_pattern(title_keywords),
    ]
    return "|".join(patterns) if patterns else None


def _build_category_data(name: str) -> Dict[str, Any] | None:
    metadata = CATEGORY_METADATA.get(name)
    if not metadata:
        return None
    data = {}
    if isinstance(metadata.get("score"), (int, float)):
        data["score"] = metadata["score"]
    return data or None


def _load_default_classes() -> List[Dict[str, Any]]:
    seed_path = Path(__file__).with_name("settings_seed_knowledgebase.v1.json")
    document = json.loads(seed_path.read_text())
    categories = sorted(
        document.get("categories") or [],
        key=lambda category: CATEGORY_PRIORITY.get(str(category.get("name") or ""), 0),
        reverse=True,
    )

    compiled = []
    for category in categories:
        name = str(category.get("name") or "").strip()
        if not name:
            continue

        regex = _build_knowledgebase_regex(category)
        entry: Dict[str, Any] = {
            "name": [name],
            "rule": {"type": "regex", "regex": regex, "ignore_case": True}
            if regex
            else {"type": "none"},
        }
        data = _build_category_data(name)
        if data:
            entry["data"] = data
        compiled.append(entry)

    compiled.append(
        {
            "name": ["Uncategorized"],
            "rule": {"type": None},
            "data": {"color": UNCATEGORIZED_COLOR},
        }
    )
    return compiled


DEFAULT_SETTINGS: Dict[str, Any] = {
    "startOfDay": "09:00",
    "startOfWeek": "Monday",
    "durationDefault": 24 * 60 * 60,
    "useColorFallback": False,
    "landingpage": "/activity",
    "theme": "auto",
    "always_active_pattern": "",
    "classes": _load_default_classes(),
    "categorizationKnowledgebaseVersion": CURRENT_CATEGORIZATION_KNOWLEDGEBASE_VERSION,
    "showYearly": False,
    "useMultidevice": False,
    "requestTimeout": 30,
    "deviceMappings": {},
}


def get_settings_defaults() -> Dict[str, Any]:
    return deepcopy(DEFAULT_SETTINGS)


def canonicalize_setting_key(key: str) -> str:
    return SETTINGS_KEY_ALIASES.get(key, key)


def _normalize_bool(value: Any, *, default: bool, strict: bool) -> bool:
    if isinstance(value, bool):
        return value
    if strict:
        raise ValueError("Expected a boolean value")
    return default


def _normalize_int(value: Any, *, default: int, strict: bool, minimum: int = 0) -> int:
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)) and int(value) == value and int(value) >= minimum:
        return int(value)
    if strict:
        raise ValueError(f"Expected an integer >= {minimum}")
    return default


def _normalize_nonempty_string(value: Any, *, default: str, strict: bool) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    if strict:
        raise ValueError("Expected a non-empty string value")
    return default


def _normalize_start_of_day(value: Any, *, default: str, strict: bool) -> str:
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                return f"{hours:02d}:{minutes:02d}"
    if strict:
        raise ValueError("Expected startOfDay in HH:MM format")
    return default


def _normalize_start_of_week(value: Any, *, default: str, strict: bool) -> str:
    if isinstance(value, str) and value in ALLOWED_START_OF_WEEK:
        return value
    if strict:
        raise ValueError("Expected startOfWeek to be Monday or Sunday")
    return default


def _normalize_theme(value: Any, *, default: str, strict: bool) -> str:
    if isinstance(value, str) and value in ALLOWED_THEME:
        return value
    if strict:
        raise ValueError("Expected theme to be one of light, dark, or auto")
    return default


def _normalize_device_mappings(value: Any, *, default: Dict[str, List[str]], strict: bool) -> Dict[str, List[str]]:
    if not isinstance(value, dict):
        if strict:
            raise ValueError("Expected deviceMappings to be an object")
        return deepcopy(default)

    normalized: Dict[str, List[str]] = {}
    for raw_group, raw_hosts in value.items():
        if not isinstance(raw_group, str):
            if strict:
                raise ValueError("Device group names must be strings")
            continue
        group_name = raw_group.strip()
        if not group_name:
            if strict:
                raise ValueError("Device group names cannot be empty")
            continue
        if not isinstance(raw_hosts, list):
            if strict:
                raise ValueError(f"Device group '{group_name}' must contain a host list")
            continue

        hosts: List[str] = []
        seen = set()
        for raw_host in raw_hosts:
            if not isinstance(raw_host, str):
                if strict:
                    raise ValueError(f"Hostnames for '{group_name}' must be strings")
                continue
            host = raw_host.strip()
            if not host or host in seen:
                continue
            hosts.append(host)
            seen.add(host)
        normalized[group_name] = hosts
    return normalized


def _normalize_category_name(value: Any, *, strict: bool) -> List[str]:
    if isinstance(value, list):
        normalized = [part.strip() for part in value if isinstance(part, str) and part.strip()]
        if normalized:
            return normalized
    if strict:
        raise ValueError("Category names must be a non-empty string list")
    return []


def _normalize_category_rule(value: Any, *, strict: bool) -> Dict[str, Any]:
    if not isinstance(value, dict):
        if strict:
            raise ValueError("Category rule must be an object")
        return {"type": "none"}

    rule_type = value.get("type")
    if rule_type is None:
        return {"type": None}
    if rule_type == "none":
        return {"type": "none"}
    if rule_type != "regex":
        if strict:
            raise ValueError("Category rule type must be regex, none, or null")
        return {"type": "none"}

    regex = value.get("regex")
    if not isinstance(regex, str) or not regex.strip():
        if strict:
            raise ValueError("Regex category rules require a non-empty regex")
        return {"type": "none"}

    normalized = {"type": "regex", "regex": regex.strip()}
    if value.get("ignore_case") is not None:
        normalized["ignore_case"] = bool(value.get("ignore_case"))
    return normalized


def _normalize_category_data(value: Any) -> Dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return deepcopy(value)


def _normalize_classes(value: Any, *, default: List[Dict[str, Any]], strict: bool) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        if strict:
            raise ValueError("Expected classes to be a list")
        return deepcopy(default)

    normalized = []
    for index, raw_category in enumerate(value):
        if not isinstance(raw_category, dict):
            if strict:
                raise ValueError(f"Category at index {index} must be an object")
            continue
        name = _normalize_category_name(raw_category.get("name"), strict=strict)
        if not name:
            if strict:
                raise ValueError(f"Category at index {index} has an invalid name")
            continue
        rule = _normalize_category_rule(raw_category.get("rule"), strict=strict)
        entry: Dict[str, Any] = {"name": name, "rule": rule}
        data = _normalize_category_data(raw_category.get("data"))
        if data:
            entry["data"] = data
        normalized.append(entry)
    return normalized


SETTING_NORMALIZERS: Dict[str, Callable[[Any, Any, bool], Any]] = {
    "startOfDay": lambda value, default, strict: _normalize_start_of_day(
        value, default=default, strict=strict
    ),
    "startOfWeek": lambda value, default, strict: _normalize_start_of_week(
        value, default=default, strict=strict
    ),
    "durationDefault": lambda value, default, strict: _normalize_int(
        value, default=default, strict=strict, minimum=1
    ),
    "useColorFallback": lambda value, default, strict: _normalize_bool(
        value, default=default, strict=strict
    ),
    "landingpage": lambda value, default, strict: _normalize_nonempty_string(
        value, default=default, strict=strict
    ),
    "theme": lambda value, default, strict: _normalize_theme(
        value, default=default, strict=strict
    ),
    "always_active_pattern": lambda value, default, strict: (
        value if isinstance(value, str) else (_raise_or_default("Expected always_active_pattern to be a string", default, strict))
    ),
    "classes": lambda value, default, strict: _normalize_classes(
        value, default=default, strict=strict
    ),
    "categorizationKnowledgebaseVersion": lambda value, default, strict: _normalize_int(
        value, default=default, strict=strict, minimum=0
    ),
    "showYearly": lambda value, default, strict: _normalize_bool(
        value, default=default, strict=strict
    ),
    "useMultidevice": lambda value, default, strict: _normalize_bool(
        value, default=default, strict=strict
    ),
    "requestTimeout": lambda value, default, strict: _normalize_int(
        value, default=default, strict=strict, minimum=1
    ),
    "deviceMappings": lambda value, default, strict: _normalize_device_mappings(
        value, default=default, strict=strict
    ),
}


def _raise_or_default(message: str, default: Any, strict: bool) -> Any:
    if strict:
        raise ValueError(message)
    return deepcopy(default)


def normalize_setting_value(key: str, value: Any, *, strict: bool) -> Any:
    canonical_key = canonicalize_setting_key(key)
    if canonical_key not in DEFAULT_SETTINGS:
        return deepcopy(value)
    default = DEFAULT_SETTINGS[canonical_key]
    normalizer = SETTING_NORMALIZERS[canonical_key]
    return normalizer(value, deepcopy(default), strict)


def normalize_settings_data(raw_data: Dict[str, Any] | None) -> Tuple[Dict[str, Any], bool]:
    source = deepcopy(raw_data or {})
    changed = False

    for alias, canonical in SETTINGS_KEY_ALIASES.items():
        if alias in source:
            if canonical not in source:
                source[canonical] = source[alias]
            del source[alias]
            changed = True

    normalized: Dict[str, Any] = {}
    for key, default in DEFAULT_SETTINGS.items():
        raw_value = source.pop(key, _MISSING)
        if raw_value is _MISSING:
            normalized[key] = deepcopy(default)
            changed = True
            continue
        normalized_value = normalize_setting_value(key, raw_value, strict=False)
        if normalized_value != raw_value:
            changed = True
        normalized[key] = normalized_value

    schema_version = source.pop("_schema_version", None)
    if schema_version != SETTINGS_SCHEMA_VERSION:
        changed = True
    normalized["_schema_version"] = SETTINGS_SCHEMA_VERSION

    for key, value in source.items():
        normalized[key] = deepcopy(value)

    return normalized, changed or normalized != (raw_data or {})
