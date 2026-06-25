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
  consumíveis pelo SysReptor: gap report, Statement of Applicability, e o
  alerta inicial (24h) / relatório detalhado (72h) do regime de notificação
  de incidentes ao CNCS via MyCiber.
- `tests/` — testes do motor (24 testes).
- `examples/demo_deliverables.py` — demo end-to-end: classificação →
  assessment → SoA → alerta de incidente.

## Estado de validação jurídica

Os setores e níveis em `data/controls/` e `nis2_engine/classification.py`
foram confirmados via fontes secundárias (CMS, Crowe, PWC) — o acesso direto
ao texto do Diário da República está bloqueado pela política de rede desta
sessão (DRE devolve 403 ao proxy). **Antes de usar com clientes reais**, os
setores, exceções de dimensão e medidas mínimas devem ser validados
artigo-a-artigo contra o Regulamento n.º 756/2026 e o DL 125/2025 publicados.

## Utilização via CLI

Depois de `pip install -e .`, fica disponível o comando `nis2`:

```bash
# 1. Classificar a entidade e gerar o relatório de autoidentificação MyCiber
nis2 classify examples/entity_camara.yaml -o out/self_identification.md

# 2. Gerar um questionário de maturidade em branco para preencher
nis2 scaffold examples/entity_camara.yaml -o answers.yaml

# 3. Correr o assessment e gerar todos os deliverables (gap report, SoA,
#    autoidentificação) num diretório de saída
nis2 assess examples/entity_camara.yaml examples/answers_camara.yaml -o out/
```

O fluxo típico de uma consultoria é: `classify` → `scaffold` → preencher o
`answers.yaml` com o cliente → `assess`. O nível-alvo é derivado da
classificação, mas pode ser forçado com `--level basico|substancial|elevado`.

Em alternativa, o motor é usável como biblioteca — ver
`examples/demo_deliverables.py`.

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
