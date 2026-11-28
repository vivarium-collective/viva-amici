"""AmiciFullReportUTCStep: one-shot full-report UTC on the engine-core contract.

Hits the real AMICI bridge: compiles a tiny antimony model with a reaction and
runs a uniform time course, asserting the canonical shape plus that reaction
fluxes are reported alongside species.
"""
import pytest

pytest.importorskip("amici")
pytest.importorskip("antimony")

from engine_core import UniformTimeCourseStep  # noqa: E402
from process_bigraph import allocate_core  # noqa: E402

from viva_amici import AmiciFullReportUTCStep  # noqa: E402

_REACTION = """
model reaction_decay
  J0: A -> B; k*A
  A = 10; B = 0; k = 0.2
end
"""


def _reaction_sbml(tmp_path) -> str:
    import antimony

    antimony.clearPreviousLoads()
    assert antimony.loadAntimonyString(_REACTION) >= 0, antimony.getLastError()
    name = antimony.getModuleNames()[-1]
    path = tmp_path / "reaction.sbml"
    path.write_text(antimony.getSBMLString(name))
    return str(path)


def test_subclasses_the_engine_core_contract():
    assert issubclass(AmiciFullReportUTCStep, UniformTimeCourseStep)
    step = AmiciFullReportUTCStep(config={"model_id": "fr_ports"}, core=allocate_core())
    assert step.inputs() == {
        "model_source": "string",
        "time": "float",
        "n_points": "integer",
    }
    assert step.outputs() == {"result": "tree"}


def test_emits_full_report_with_species_and_fluxes(tmp_path):
    model = _reaction_sbml(tmp_path)
    step = AmiciFullReportUTCStep(
        config={"model_id": "fr_reaction_decay"}, core=allocate_core()
    )
    out = step.update({"model_source": model, "time": 10.0, "n_points": 11})
    r = out["result"]

    assert set(r) == {"time", "columns", "values"}
    assert len(r["time"]) == 11
    assert len(r["values"]) == 11
    assert all(len(row) == len(r["columns"]) for row in r["values"])
    assert all(isinstance(v, float) for row in r["values"] for v in row)

    cols = set(r["columns"])
    assert {"A", "B"} <= cols   # species (state ids)
    assert "J0" in cols         # reaction flux (flux_J0 -> J0)


def test_rejects_degenerate_n_points(tmp_path):
    model = _reaction_sbml(tmp_path)
    step = AmiciFullReportUTCStep(
        config={"model_id": "fr_npts"}, core=allocate_core()
    )
    with pytest.raises(ValueError, match="n_points must be >= 2"):
        step.update({"model_source": model, "time": 10.0, "n_points": 1})
