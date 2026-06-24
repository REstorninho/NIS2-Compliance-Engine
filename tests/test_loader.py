from nis2_engine import load_controls


def test_load_controls_returns_valid_unique_controls():
    controls = load_controls()
    assert len(controls) > 0
    ids = [c.id for c in controls]
    assert len(ids) == len(set(ids))


def test_each_control_has_required_fields():
    for control in load_controls():
        assert control.id
        assert control.title
        assert control.qnrcs_function in {
            "Governar",
            "Identificar",
            "Proteger",
            "Detetar",
            "Responder",
            "Recuperar",
        }
        assert set(control.levels) == {"basico", "substancial", "elevado"}
