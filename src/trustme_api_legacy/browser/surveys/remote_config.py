from __future__ import annotations

from trustme_api_legacy._module_shim import bind_legacy_module

bind_legacy_module(globals(), "browser/surveys/remote_config.py", "browser.surveys.remote_config")
