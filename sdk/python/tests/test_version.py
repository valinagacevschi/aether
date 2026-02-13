from __future__ import annotations

import aether


def test_package_exposes_version() -> None:
    assert isinstance(aether.__version__, str)
    assert aether.__version__
