"""
Deprecation functionally gracefully degrade if degraded module or <py3.13

If you're not writing "must not crash" code, use the deprecated package directly.  It's good.

However if are writing code that must not fail, this can be used, just be aware
that it has a dependency on the deprecated module, thus you should update your deps
accordingly.  This just falls back to crappier implementations if the deprecated module
is broken for some reason, allowing snakeoil to still be importable.
"""

__all__ = ("deprecated",)

import sys
import warnings
from contextlib import contextmanager

try:
    from deprecated import deprecated  # pyright: ignore[reportAssignmentType]
except ImportError:
    warnings.warn(
        "deprecated module could not be imported.  Deprecation messages may not be shown"
    )
    if sys.version_info >= (3, 12, 0):
        # shim it, but drop the deprecated.deprecated metadata.
        def deprecated(message, *args, **kwargs):
            return warnings.deprecated(message)
    else:
        # stupid shitty python 3.11/3.12...
        def deprecated(_message, *args, **kwargs):
            """
            This is disabled in full due to the deprecated module failing to import, and
            inability to fallback since the python version is less than 3.13
            """

            def f(thing):
                return thing

            return f


@contextmanager
def suppress_deprecation_warning():
    # see https://docs.python.org/3/library/warnings.html#temporarily-suppressing-warnings
    with warnings.catch_warnings():
        warnings.simplefilter(action="ignore", category=DeprecationWarning)
        yield
