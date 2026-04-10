from backend_overlay.__about__ import __version__

__all__ = [
    "__version__",
    "main",
]


def __getattr__(name):
    if name == "main":
        from backend_overlay.main import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
