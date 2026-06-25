from nis2_engine import build_audit_report, load_controls
from nis2_engine.models import Control


def test_audit_report_flags_all_controls_pending_by_default():
    controls = load_controls()
    report = build_audit_report(controls)

    assert report.total_controls == len(controls)
    assert len(report.pending_controls) == len(controls)
    assert report.confirmed_controls == []
    assert report.classification_status == "por_validar"
    assert not report.fully_validated


def test_audit_report_separates_confirmed_from_pending():
    confirmed = Control(
        id="GOV-99",
        title="Controlo confirmado",
        qnrcs_function="Governar",
        levels={"basico": True, "substancial": True, "elevado": True},
        evidence_type="documental",
        estado_validacao="confirmado",
        fonte="DRE - Art. 21",
    )
    pending = Control(
        id="GOV-98",
        title="Controlo por validar",
        qnrcs_function="Governar",
        levels={"basico": True, "substancial": True, "elevado": True},
        evidence_type="documental",
    )
    report = build_audit_report([confirmed, pending])

    assert report.confirmed_controls == [confirmed]
    assert report.pending_controls == [pending]
    assert report.pending_pct == 50.0
