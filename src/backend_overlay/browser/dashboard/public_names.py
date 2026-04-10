from typing import Optional


KNOWN_BUCKET_LABELS = {
    "aw-watcher-window": "trustme-window bucket",
    "aw-watcher-afk": "trustme-presence bucket",
    "aw-watcher-firefox": "trustme-browser bucket",
    "aw-watcher-web-firefox": "trustme-browser bucket",
    "aw-watcher-vscode": "trustme-editor bucket",
    "aw-stopwatch": "trustme-away bucket",
}


KNOWN_MODULE_LABELS = {
    "aw-server": "trustme-backend",
    "aw-watcher-afk": "trustme-presence",
    "aw-watcher-window": "trustme-window",
    "aw-watcher-input": "trustme-input",
    "aw-watcher-web": "trustme-browser",
    "aw-watcher-vscode": "trustme-editor",
    "aw-notify": "trustme-checkins",
}


def bucket_display_name(bucket_id: str, hostname: Optional[str] = None) -> str:
    hostname = hostname or ""
    base = bucket_id or ""
    suffix = f"_{hostname}" if hostname else ""
    if suffix and base.endswith(suffix):
        base = base[: -len(suffix)]

    if base in KNOWN_BUCKET_LABELS:
        return KNOWN_BUCKET_LABELS[base]
    if base.startswith("aw-watcher-"):
        return f"trustme-{base[len('aw-watcher-'):]} bucket"
    if base.startswith("aw-"):
        return f"trustme-{base[len('aw-'):]} bucket"
    return f"{base} bucket" if base else "trustme bucket"


def module_display_name(module_name: str) -> str:
    if module_name in KNOWN_MODULE_LABELS:
        return KNOWN_MODULE_LABELS[module_name]
    if module_name.startswith("aw-"):
        return f"trustme-{module_name[len('aw-'):]}"
    return module_name
