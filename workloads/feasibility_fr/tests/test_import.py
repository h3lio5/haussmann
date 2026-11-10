from importlib.resources import files

import feasibility_fr


def test_package_imports_and_is_typed() -> None:
    assert feasibility_fr.__name__ == "feasibility_fr"
    assert files("feasibility_fr").joinpath("py.typed").is_file()
