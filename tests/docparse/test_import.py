from haussmann import docparse


def test_module_imports() -> None:
    assert docparse.__name__ == "haussmann.docparse"
