# NIS2 Compliance Engine

Plataforma-metodologia de conformidade com o regime jurídico da cibersegurança
(DL 125/2025 + Regulamento n.º 756/2026), alinhada com o QNRCS, NIST CSF 2.0,
ISO/IEC 27001:2022 e CIS Controls v8.

## Estrutura

- `data/controls/` — corpus de controlos em YAML. Cada ficheiro é um controlo
  com o crosswalk NIS2 ↔ QNRCS ↔ ISO 27001 ↔ CIS ↔ RGPD, o nível mínimo exigido
  (básico/substancial/elevado) e o tipo de evidência esperado.
- `data/schema/control.schema.json` — JSON Schema de validação dos controlos.
- `nis2_engine/` — motor Python (sem UI):
  - `models.py` — dataclasses (`Control`, `Entity`, `AssessmentAnswer`, ...).
  - `loader.py` — carrega e valida os controlos a partir de `data/controls/`.
  - `classification.py` — motor de âmbito: essencial / importante / entidade
    pública relevante, regra de dimensão, exceções setoriais → nível de risco
    exigido.
  - `assessment.py` — motor de maturidade: cruza respostas com os controlos
    exigidos para o nível do cliente, calcula gap-analysis e roadmap.
- `templates/deliverables/` — templates Jinja2 para gerar relatórios
  (gap report, Statement of Applicability) consumíveis pelo SysReptor.
- `tests/` — testes do motor.

## Fora de âmbito deste repositório

Recolha automatizada de evidência técnica (scans, Wazuh, etc.) e a camada de
IA local correm fora deste repositório. Este repositório define apenas o
*contrato* de dados (schema de controlo e de evidência) que essas peças têm
de respeitar.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```
