import pytest


def test_tui_module_builds_app_class():
    textual = pytest.importorskip("textual")
    assert textual is not None

    from src.tgxml.tui_app import TgXmlTextualApp

    app_cls = TgXmlTextualApp().build()
    assert app_cls is not None
