"""The benchmark scenarios of this workload, by id."""

from collections.abc import Mapping

from feasibility_fr.benchmark.scenario import Scenario
from feasibility_fr.benchmark.scenarios import champagnole_ecole, metz_vigny

SCENARIOS: Mapping[str, Scenario] = {
    scenario.spec.id: scenario for scenario in (metz_vigny.SCENARIO, champagnole_ecole.SCENARIO)
}
