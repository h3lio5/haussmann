from importlib.resources import files


def test_platform_ships_type_marker() -> None:
    assert files("haussmann").joinpath("py.typed").is_file()
