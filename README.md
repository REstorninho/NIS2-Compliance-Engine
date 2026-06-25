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
  - `assessment.py` — motor de maturidade graduada (escala 0-5): cruza
    respostas com os controlos exigidos para o nível do cliente, calcula
    gap-analysis, score de conformidade e maturidade média por função QNRCS.
  - `roadmap.py` — agrupa os gaps por remediar num roadmap faseado por
    prioridade (0-3 / 3-6 / 6-12 meses).
  - `audit.py` — relatório de rastreabilidade jurídica: que controlos e que
    classificação setorial já foram confirmados artigo-a-artigo contra o
    texto oficial (campo `estado_validacao` em cada `Control`), e o que
    continua por validar via fontes secundárias. Gera também um checklist de
    validação manual em CSV (`build_validation_checklist`), uma linha por
    controlo (+ a classificação setorial) com o crosswalk atualmente citado e
    colunas em branco para um revisor confirmar artigo-a-artigo contra o DRE.
  - `history.py` — snapshots serializáveis de cada `AssessmentResult` (score,
    maturidade por função, estado de cada controlo), gravados em disco com
    timestamp; permite listar (`nis2 history`) e comparar a evolução de uma
    entidade entre dois assessments (`nis2 progress`).
  - `charts.py` — gráfico radar (teia) de maturidade por função QNRCS em SVG
    puro, sem dependências externas, pronto a embeber em HTML/markdown.
- `templates/deliverables/` — templates Jinja2 para gerar relatórios
  consumíveis pelo SysReptor: gap report (com maturidade por função), roadmap
  de remediação faseado, Statement of Applicability, plano de recolha de
  evidência (deriva do `evidence_contract` de cada controlo), relatório de
  auditoria jurídica, relatório de evolução entre assessments, relatório HTML
  imprimível (radar embebido + marca do consultor), e o alerta inicial (24h)
  / relatório detalhado (72h) do regime de notificação de incidentes ao CNCS
  via MyCiber.
- `templates/policies/` — pacote de políticas/procedimentos chave que servem
  de evidência documental: resposta a incidentes, segurança de fornecedores e
  continuidade de negócio/BC-DR.
- `tests/` — testes do motor (61 testes).
- `examples/demo_deliverables.py` — demo end-to-end: classificação →
  assessment → SoA → alerta de incidente.

## Estado de validação jurídica

Os setores e níveis em `data/controls/` e `nis2_engine/classification.py`
foram confirmados via fontes secundárias (CMS, Crowe, PWC) — o acesso direto
ao texto do Diário da República está bloqueado pela política de rede desta
sessão (DRE devolve 403 ao proxy). **Antes de usar com clientes reais**, os
setores, exceções de dimensão e medidas mínimas devem ser validados
artigo-a-artigo contra o Regulamento n.º 756/2026 e o DL 125/2025 publicados.

Este estado é rastreado de forma explícita e auditável: cada `Control` tem um
campo `estado_validacao` (`confirmado` / `por_validar`, por omissão
`por_validar`) e `fonte`. Corre `nis2 audit` para ver, em qualquer momento,
exatamente quantos controlos já foram confirmados artigo-a-artigo e quantos
continuam pendentes — à medida que cada controlo for validado contra o texto
oficial, basta atualizar o respetivo YAML em `data/controls/` com
`estado_validacao: confirmado` e `fonte: ...`.

Para facilitar essa validação manual (sem acesso direto ao DRE nesta sessão),
`nis2 audit --checklist <ficheiro.csv>` exporta um checklist em CSV — uma
linha por controlo (mais uma para a classificação setorial) com o artigo
NIS2/Regulamento atualmente citado no crosswalk e colunas em branco
(`artigo_confirmado_dre`, `data_confirmacao`, `confirmado_por`,
`observacoes`) para um revisor (ex. jurídico) preencher ao confrontar cada
linha com o texto oficial publicado.

## Utilização via CLI

Depois de `pip install -e .`, fica disponível o comando `nis2`:

```bash
# 1. Classificar a entidade e gerar o relatório de autoidentificação MyCiber
nis2 classify examples/entity_camara.yaml -o out/self_identification.md

# 2. Gerar um questionário de maturidade em branco para preencher
nis2 scaffold examples/entity_camara.yaml -o answers.yaml

# 3. Correr o assessment e gerar todos os deliverables (gap report, roadmap,
#    SoA, autoidentificação, plano de recolha de evidência, radar SVG e
#    relatório HTML imprimível com a marca do consultor)
nis2 assess examples/entity_camara.yaml examples/answers_camara.yaml -o out/ --brand "Acme CyberSec"

# 4. Gerar o pacote de políticas chave (evidência documental) para a entidade
nis2 policies examples/entity_camara.yaml -o out/politicas --approver "Nome do Responsável"

# 5. Ver o estado de rastreabilidade jurídica do corpus (confirmado vs. por validar)
#    e gerar o checklist de validação manual (CSV) para confirmar cada
#    controlo artigo-a-artigo contra o texto oficial do DRE
nis2 audit -o out/audit_report.md --checklist out/checklist_validacao_juridica.csv

# 6. Gravar um snapshot do assessment para comparação futura, listar o histórico
#    e comparar os dois assessments mais recentes da mesma entidade
nis2 assess examples/entity_camara.yaml examples/answers_camara.yaml -o out/ --history-dir out/.history
nis2 history "Câmara Municipal de Exemplo" --history-dir out/.history
nis2 progress "Câmara Municipal de Exemplo" --history-dir out/.history -o out/relatorio_evolucao.md

# 7. Gerar o alerta inicial (24h) e o relatório detalhado (72h) de um
#    incidente para notificação ao CNCS via MyCiber (Art. 23 DL 125/2025)
nis2 incident examples/entity_camara.yaml examples/incident_camara.yaml -o out/incidente
```

> O relatório HTML (`out/report.html`) é self-contained e imprimível para PDF
> a partir de qualquer browser (Ctrl/Cmd+P → Guardar como PDF), com o gráfico
> radar de maturidade embebido — não requer dependências externas.

O fluxo típico de uma consultoria é: `classify` → `scaffold` → preencher o
`answers.yaml` com o cliente → `assess`. O nível-alvo é derivado da
classificação, mas pode ser forçado com `--level basico|substancial|elevado`.

Em alternativa, o motor é usável como biblioteca — ver
`examples/demo_deliverables.py`.

## Fora de âmbito deste repositório

Recolha automatizada de evidência técnica (scans, Wazuh, etc.) e a camada de
IA local correm fora deste repositório. Este repositório define apenas o
*contrato* de dados (schema de controlo e de evidência) que essas peças têm
de respeitar — o comando `nis2 assess` materializa esse contrato no
`evidence_plan.md`, que lista, por controlo, a fonte e os campos que a camada
de recolha deve fornecer.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```
