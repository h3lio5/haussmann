from haussmann import buildkit


def test_module_imports() -> None:
    assert buildkit.__name__ == "haussmann.buildkit"
