"""Write every scenario's files and manifest to disk.

Run: python -m feasibility_fr.benchmark.render <benchmark_data_dir>
"""

import sys
from pathlib import Path

from feasibility_fr.benchmark.scenario import generate
from feasibility_fr.benchmark.scenarios import SCENARIOS
from haussmann.evalkit.generator import write

FILES_DIR = "files"


def render_all(data_dir: Path) -> None:
    for scenario_id, scenario in SCENARIOS.items():
        write(generate(scenario), data_dir / scenario_id / FILES_DIR)


if __name__ == "__main__":
    render_all(Path(sys.argv[1]))
