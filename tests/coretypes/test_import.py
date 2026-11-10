from haussmann import coretypes


def test_module_imports() -> None:
    assert coretypes.__name__ == "haussmann.coretypes"
