from __future__ import annotations

import math

# Gráfico radar (teia) de maturidade por função QNRCS, gerado como SVG puro —
# sem dependências externas (matplotlib, etc.), para poder ser embebido
# diretamente em deliverables markdown/HTML e renderizado em qualquer browser
# ou no SysReptor.

# Ordem canónica das funções do QNRCS, para que o radar saia sempre consistente.
QNRCS_FUNCTION_ORDER = [
    "Governar",
    "Identificar",
    "Proteger",
    "Detetar",
    "Responder",
    "Recuperar",
]

_MAX_MATURITY = 5.0


def _point(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    return (
        cx + radius * math.cos(angle),
        cy + radius * math.sin(angle),
    )


def render_maturity_radar_svg(
    maturity_by_function: dict[str, float],
    *,
    size: int = 420,
    title: str = "Maturidade por função (QNRCS)",
) -> str:
    """Gera um radar SVG (0-5) da maturidade média por função QNRCS.

    `maturity_by_function` mapeia o nome da função → maturidade média (0-5).
    Funções em falta no dicionário são tratadas como 0.
    """
    functions = [f for f in QNRCS_FUNCTION_ORDER if f in maturity_by_function]
    # Inclui quaisquer funções fora da ordem canónica (defensivo).
    functions += [f for f in maturity_by_function if f not in functions]
    n = len(functions)
    if n < 3:
        # Um radar com menos de 3 eixos não tem significado geométrico.
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="40"><text x="8" y="24">Dados insuficientes para o radar.</text></svg>'

    cx = cy = size / 2
    margin = 70
    max_radius = size / 2 - margin
    # Ângulos começam no topo (-90°) e progridem no sentido horário.
    angles = [(-math.pi / 2) + (2 * math.pi * i / n) for i in range(n)]

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" font-family="sans-serif">'
    )
    parts.append(f'<rect width="{size}" height="{size}" fill="#ffffff"/>')
    parts.append(
        f'<text x="{cx}" y="24" text-anchor="middle" font-size="15" '
        f'font-weight="bold" fill="#1a1a1a">{title}</text>'
    )

    # Anéis da grelha (1..5).
    for ring in range(1, int(_MAX_MATURITY) + 1):
        r = max_radius * ring / _MAX_MATURITY
        ring_points = " ".join(
            f"{x:.1f},{y:.1f}" for x, y in (_point(cx, cy, r, a) for a in angles)
        )
        parts.append(
            f'<polygon points="{ring_points}" fill="none" '
            f'stroke="#dddddd" stroke-width="1"/>'
        )

    # Eixos + rótulos das funções.
    for func, angle in zip(functions, angles):
        ax, ay = _point(cx, cy, max_radius, angle)
        parts.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ax:.1f}" y2="{ay:.1f}" '
            f'stroke="#cccccc" stroke-width="1"/>'
        )
        lx, ly = _point(cx, cy, max_radius + 22, angle)
        anchor = "middle"
        if lx > cx + 1:
            anchor = "start"
        elif lx < cx - 1:
            anchor = "end"
        value = maturity_by_function.get(func, 0.0)
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="12" fill="#333333">{func}</text>'
        )
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 14:.1f}" text-anchor="{anchor}" '
            f'font-size="10" fill="#888888">{value:g}/5</text>'
        )

    # Polígono de dados.
    data_points = []
    for func, angle in zip(functions, angles):
        value = max(0.0, min(_MAX_MATURITY, maturity_by_function.get(func, 0.0)))
        r = max_radius * value / _MAX_MATURITY
        data_points.append(_point(cx, cy, r, angle))
    data_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_points)
    parts.append(
        f'<polygon points="{data_str}" fill="#2b6cb0" fill-opacity="0.30" '
        f'stroke="#2b6cb0" stroke-width="2"/>'
    )
    for x, y in data_points:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#2b6cb0"/>')

    parts.append("</svg>")
    return "".join(parts)
