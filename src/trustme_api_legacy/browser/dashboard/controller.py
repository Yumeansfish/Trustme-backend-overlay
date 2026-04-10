from __future__ import annotations

from trustme_api_legacy._module_shim import bind_legacy_module

bind_legacy_module(globals(), "browser/dashboard/controller.py", "browser.dashboard.controller")
