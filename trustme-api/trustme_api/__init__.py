from trustme_api.__about__ import __version__

__all__ = [
    "__version__",
    "main",
]


def __getattr__(name):
    if name == "main":
        from trustme_api.main import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
