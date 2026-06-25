import xml.dom.minidom

from nis2_engine.charts import QNRCS_FUNCTION_ORDER, render_maturity_radar_svg


def _full_maturity() -> dict[str, float]:
    return {f: 3.0 for f in QNRCS_FUNCTION_ORDER}


def test_radar_is_well_formed_svg():
    svg = render_maturity_radar_svg(_full_maturity())
    # Não deve lançar — SVG bem-formado.
    xml.dom.minidom.parseString(svg)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_radar_includes_function_labels():
    svg = render_maturity_radar_svg(_full_maturity())
    for function in QNRCS_FUNCTION_ORDER:
        assert function in svg


def test_radar_clamps_out_of_range_values():
    # Valores fora de [0,5] não devem rebentar nem produzir coordenadas inválidas.
    svg = render_maturity_radar_svg({f: 99.0 for f in QNRCS_FUNCTION_ORDER})
    xml.dom.minidom.parseString(svg)
    svg_low = render_maturity_radar_svg({f: -10.0 for f in QNRCS_FUNCTION_ORDER})
    xml.dom.minidom.parseString(svg_low)


def test_radar_handles_too_few_axes():
    svg = render_maturity_radar_svg({"Governar": 2.0, "Proteger": 3.0})
    assert "Dados insuficientes" in svg
