from haussmann import app


def test_module_imports() -> None:
    assert app.__name__ == "haussmann.app"
