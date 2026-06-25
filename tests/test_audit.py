from nis2_engine import (
    VALIDATION_CHECKLIST_FIELDS,
    build_audit_report,
    build_validation_checklist,
    load_controls,
    render_validation_checklist_csv,
)
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


def test_validation_checklist_includes_classification_and_all_controls():
    controls = load_controls()
    rows = build_validation_checklist(controls)

    assert rows[0]["item_id"] == "CLASSIFICACAO-SETORIAL"
    assert rows[0]["estado_validacao_atual"] == "por_validar"

    control_rows = rows[1:]
    assert len(control_rows) == len(controls)
    assert {row["item_id"] for row in control_rows} == {c.id for c in controls}
    for row in rows:
        assert set(row.keys()) == set(VALIDATION_CHECKLIST_FIELDS)
        # Colunas a preencher pelo revisor começam em branco.
        assert row["artigo_confirmado_dre"] == ""
        assert row["data_confirmacao"] == ""
        assert row["confirmado_por"] == ""


def test_validation_checklist_csv_has_header_and_one_row_per_item():
    controls = load_controls()
    rows = build_validation_checklist(controls)
    csv_text = render_validation_checklist_csv(rows)

    lines = csv_text.strip().splitlines()
    assert lines[0] == ",".join(VALIDATION_CHECKLIST_FIELDS)
    assert len(lines) == len(rows) + 1
