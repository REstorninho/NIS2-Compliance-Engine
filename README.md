# NIS2 Compliance Engine

Plataforma-metodologia de conformidade com o regime jurídico da cibersegurança
(DL 125/2025 + Regulamento n.º 756/2026), alinhada com o QNRCS, NIST CSF 2.0,
ISO/IEC 27001:2022 e CIS Controls v8.

Cobre o ciclo de conformidade de ponta a ponta: **classificação de âmbito**
(essencial / importante / entidade pública relevante / fora de âmbito),
**autoavaliação de maturidade** e gap-analysis, **roadmap** de remediação
faseado, **deliverables** prontos a entregar (gap report, Statement of
Applicability, plano de recolha de evidência, relatório HTML imprimível,
pacote de políticas), **notificação de incidentes** ao CNCS via MyCiber e
**rastreabilidade jurídica** do corpus. Há duas portas de entrada: um
formulário **HTML** que corre no browser (`nis2 form`) e uma **CLI** sobre
ficheiros YAML — a primeira exporta YAML que alimenta a segunda.

## Instalação

Pacote Python puro (sem build nem compilação). Requer **Python ≥ 3.11** e
`git`. As dependências (`pyyaml`, `jsonschema`, `jinja2`) são instaladas
automaticamente.

```bash
# 1. Clonar o repositório
git clone https://github.com/REstorninho/NIS2-Compliance-Engine.git
cd NIS2-Compliance-Engine

# 2. (Recomendado) criar e ativar um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instalar o pacote em modo editável
pip install -e .
```

Isto regista o comando **`nis2`** no PATH. Confirma com:

```bash
nis2 --version
nis2 --help
```

**Para desenvolvimento** (acrescenta o `pytest` e corre a suite de testes):

```bash
pip install -e ".[dev]"
pytest
```

> Notas: o `-e` (editável) faz com que alterações ao código fiquem ativas sem
> reinstalar. Se o comando `nis2` não aparecer após o install, normalmente é o
> ambiente virtual não estar ativado ou o diretório de *scripts* do Python não
> estar no PATH — `nis2 --version` ajuda a despistar.

## Estrutura

- `CLAUDE.md` — system prompt do copiloto **REGENTE**: identidade e papel,
  base normativa autoritativa (DL 125/2025 + Regulamento n.º 756/2026, Anexos
  I a IV), regras de raciocínio regulatório (qualificação, matriz de risco,
  seleção de medidas, notificação de incidentes), comportamento operacional e
  limites/salvaguardas. Carregado automaticamente pelo Claude Code ao
  trabalhar neste repositório.
- `data/controls/` — corpus de controlos em YAML. Cada ficheiro é um controlo
  com o crosswalk NIS2 ↔ QNRCS ↔ ISO 27001 ↔ CIS ↔ RGPD, o nível mínimo exigido
  (básico/substancial/elevado) e o tipo de evidência esperado.
- `data/schema/control.schema.json` — JSON Schema de validação dos controlos.
- `data/sector_profiles/` — perfis setoriais pré-preenchidos em YAML (um por
  vertical: autarquia, junta de freguesia, hotelaria, turismo).
- `nis2_engine/` — motor Python (sem UI):
  - `models.py` — dataclasses (`Control`, `Entity`, `AssessmentAnswer`, ...).
  - `loader.py` — carrega e valida os controlos a partir de `data/controls/`.
  - `classification.py` — motor de âmbito: essencial / importante / entidade
    pública relevante, regra de dimensão, exceções setoriais → nível de risco
    exigido.
  - `risk_matrix.py` — Matriz de Risco do Anexo II: `valor = Probabilidade ×
    Impacto × (Dimensão/3) × Tipo de setor` por cenário, soma, mapeamento para
    Básico/Substancial/Elevado (0–99 / 100–199 / 200–1200) e regra de
    agregação do art. 30.º (nível efetivo = mais exigente entre matriz e tipo
    de entidade). Deriva dimensão (G/M/P) e tipo de setor (Importância Crítica
    / Outros) da entidade.
  - `deadlines.py` — calendário de obrigações da entidade a partir da data de
    qualificação/notificação (lista de ativos art. 32.º, relatório anual,
    designação de responsável/ponto de contacto), com estado de cada prazo
    (vencido / a vencer / futuro).
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
    timestamp; permite listar (`nis2 history`), comparar a evolução de uma
    entidade entre dois assessments (`nis2 progress`) e construir a vista
    agregada da carteira de clientes (`nis2 portfolio`).
  - `incident.py` — prazos do regime de notificação (24h/72h/1 mês), a
    triagem de impacto significativo (Reg. UE 2024/2690, art. 3.º): veredicto
    fundamentado, gatilho de alerta precoce e acionamento do RGPD/CNPD; e a
    duração do impacto significativo (deteção → fim) para as fases finais.
  - `charts.py` — gráfico radar (teia) de maturidade por função QNRCS em SVG
    puro, sem dependências externas, pronto a embeber em HTML/markdown.
  - `profiles.py` — perfis setoriais pré-preenchidos (autarquias, juntas de
    freguesia, hotelaria, turismo): entidade tipo, cenários de risco habituais,
    ativos críticos, notas de prioridade e **nota de âmbito** (decisiva para os
    verticais que só entram em âmbito indiretamente). Os perfis são dados
    (`data/sector_profiles/*.yaml`), não código: `nis2 profile <id>` materializa
    `entity.yaml` + `scenarios.yaml` prontos a alimentar `nis2 risk`/`assess`.
  - `dossier.py` — agrega os deliverables Markdown num único **dossier HTML**
    com a marca do consultor (capa + índice + `@media print` com quebras de
    página), pronto a "Imprimir → Guardar como PDF". Conversor de Markdown
    próprio (subconjunto dos templates), zero dependências novas; `--pdf`
    exporta PDF de forma oportunista (weasyprint ou Chromium, se disponíveis).
- `templates/web/` — formulário HTML self-contained (`nis2 form`) para correr
  todo o fluxo no browser, sem servidor: (1) **classificação de âmbito** em
  tempo real (replica `classify_entity`); (2) **Matriz de Risco** (Anexo II) —
  enumeração de cenários (ator/probabilidade/impacto) com cálculo ao vivo do
  valor de risco e do nível efetivo, que passa a alimentar a autoavaliação
  (replica `risk_matrix.py`); (3) **autoavaliação de maturidade** — o
  questionário dos controlos exigidos para o nível resultante, com cálculo ao
  vivo de score, maturidade por função e roadmap de gaps por fase (replica
  `run_assessment` + `build_remediation_roadmap`); (4) **relatório HTML**
  self-contained, gerado no browser com o radar de maturidade embebido
  (replica `render_maturity_radar_svg` + `report.html`); (5) **histórico**
  local (localStorage). As listas de setores, a regra de dimensão, o corpus de
  controlos e os fatores/limiares da matriz de risco são injetados da fonte de
  verdade Python (paridade verificada com Playwright, incluindo o polígono do
  radar e o nível efetivo da matriz), pelo que o formulário nunca diverge do
  motor. Exporta o perfil e as respostas em YAML para alimentar a
  CLI (`classify`/`scaffold`/`assess`), o relatório em HTML e o histórico em
  CSV.
- `templates/deliverables/` — templates Jinja2 para gerar relatórios
  consumíveis pelo SysReptor: gap report (com maturidade por função), roadmap
  de remediação faseado, Statement of Applicability, plano de recolha de
  evidência (deriva do `evidence_contract` de cada controlo), relatório de
  auditoria jurídica, relatório de evolução entre assessments, relatório HTML
  imprimível (radar embebido + marca do consultor), o **ciclo completo de
  notificação de incidentes** ao CNCS via MyCiber — alerta inicial (24h),
  relatório detalhado (72h), fim do impacto significativo (art. 43.º) e
  relatório final/intercalar (art. 44.º) —, a **triagem de impacto
  significativo** do incidente, a **Matriz de Risco** (Anexo II), o
  **calendário de obrigações**, a **carteira de clientes**, e o **crosswalk
  dual NIS2 ↔ ISO/IEC 27001/27002:2022** + checklist de documentos
  obrigatórios do SGSI (ver secção seguinte).
- `nis2_engine/iso27001.py` — reagrupa o mesmo `AssessmentResult` (sem
  reavaliar nada) pela ótica da ISO/IEC 27001/27002:2022: cobertura por tema
  (Organizacionais/Pessoas/Físicos/Tecnológicos, derivado do prefixo do Anexo
  A já citado no crosswalk de cada controlo) e por medida mínima do Art. 21.º,
  n.º 2 da NIS2 (a-j, com o catálogo ISO 27002 de referência por medida).
  Inclui também a lista dos 11 documentos mínimos exigidos por um SGSI
  certificável (`ISO27001_MANDATORY_DOCUMENTS`). Pensado para o consultor que
  oferece certificação ISO 27001 como caminho de maturidade adicional sobre o
  trabalho de conformidade NIS2 já feito com o cliente.
- `templates/policies/` — pacote de políticas/procedimentos chave que servem
  de evidência documental: resposta a incidentes, segurança de fornecedores e
  continuidade de negócio/BC-DR.
- `tests/` — testes do motor (122 testes).
- `examples/demo_deliverables.py` — demo end-to-end: classificação →
  assessment → SoA → alerta de incidente.

## Estado de validação jurídica

Os setores e níveis em `data/controls/` e `nis2_engine/classification.py`
foram confirmados via fontes secundárias (CMS, Crowe, PWC) e **ainda não**
artigo-a-artigo contra o texto oficial publicado em Diário da República.
**Antes de usar com clientes reais**, os setores, exceções de dimensão e
medidas mínimas devem ser validados contra o Regulamento n.º 756/2026 e o
DL 125/2025 publicados.

Este estado é rastreado de forma explícita e auditável: cada `Control` tem um
campo `estado_validacao` (`confirmado` / `por_validar`, por omissão
`por_validar`) e `fonte`. Corre `nis2 audit` para ver, em qualquer momento,
exatamente quantos controlos já foram confirmados artigo-a-artigo e quantos
continuam pendentes — à medida que cada controlo for validado contra o texto
oficial, basta atualizar o respetivo YAML em `data/controls/` com
`estado_validacao: confirmado` e `fonte: ...`.

Para facilitar essa validação manual, `nis2 audit --checklist <ficheiro.csv>`
exporta um checklist em CSV — uma
linha por controlo (mais uma para a classificação setorial) com o artigo
NIS2/Regulamento atualmente citado no crosswalk e colunas em branco
(`artigo_confirmado_dre`, `data_confirmacao`, `confirmado_por`,
`observacoes`) para um revisor (ex. jurídico) preencher ao confrontar cada
linha com o texto oficial publicado.

## Utilização via CLI

Depois da [instalação](#instalação), fica disponível o comando `nis2`. Erros
comuns (ficheiro em falta, campo obrigatório por preencher, YAML inválido)
devolvem uma mensagem clara em `stderr` e código de saída 1 — não um
*traceback* Python. `nis2 --version` mostra a versão instalada.

| Comando | O que faz |
|---|---|
| `nis2 form` | Gera o formulário HTML que corre classificação + autoavaliação de maturidade + roadmap no browser (com histórico local). |
| `nis2 profiles` | Lista os perfis setoriais pré-preenchidos (autarquias, juntas de freguesia, hotelaria, turismo). |
| `nis2 profile` | Materializa um perfil setorial em `entity.yaml` + `scenarios.yaml` prontos a usar, com a nota de âmbito do setor. |
| `nis2 list-controls` | Lista o catálogo de controlos QNRCS (filtrável por `--level`/`--function`). |
| `nis2 classify` | Classifica a entidade e gera o relatório de autoidentificação MyCiber. |
| `nis2 risk` | Aplica a Matriz de Risco (Anexo II) a cenários e determina o nível exigido (matriz + agregação art. 30.º). |
| `nis2 scaffold` | Gera o questionário de maturidade em branco para o nível-alvo. |
| `nis2 assess` | Corre o assessment e gera todos os deliverables (gap report, roadmap, SoA, evidência, radar, HTML, crosswalk ISO 27001). `--risk` deriva o nível da matriz. |
| `nis2 policies` | Gera o pacote de políticas chave (resposta a incidentes, fornecedores, BC/DR). |
| `nis2 audit` | Relatório de rastreabilidade jurídica + checklist de validação manual (`--checklist`). |
| `nis2 history` | Lista os snapshots de assessment gravados para uma entidade. |
| `nis2 progress` | Compara os dois assessments mais recentes e gera o relatório de evolução. |
| `nis2 portfolio` | Vista agregada da carteira de clientes (nível, score, maturidade, tendência por entidade). |
| `nis2 deadlines` | Calendário de obrigações da entidade (lista de ativos art. 32.º, relatório anual, designação). |
| `nis2 incident` | Ciclo completo de notificação ao CNCS: triagem de impacto significativo, alerta inicial (24h), relatório detalhado (72h), fim do impacto significativo (art. 43.º) e relatório final/intercalar (art. 44.º, 1 mês). |
| `nis2 dossier` | Agrega os deliverables Markdown de uma pasta num dossier HTML com a marca do consultor (capa + índice + impressão); `--pdf` exporta PDF se houver motor disponível. |

```bash
# 0a. Gerar um formulário HTML que corre TODO o fluxo no browser, sem editar
#     YAML: classifica o âmbito, apresenta o questionário de maturidade do
#     nível resultante e calcula score/roadmap ao vivo, com histórico local.
#     Os botões "Descarregar perfil/respostas (YAML)" alimentam os comandos abaixo.
nis2 form -o out/classificador.html --brand "Acme CyberSec"

# 0b. Consultar o catálogo de controlos QNRCS antes de preencher o entity.yaml
#     (filtrável por --level ou --function)
nis2 list-controls --level substancial

# 0c. (Atalho por setor) Partir de um perfil pré-preenchido em vez de escrever
#     o entity.yaml do zero. Gera entity.yaml + scenarios.yaml e mostra a nota
#     de âmbito do setor (ex.: hotelaria/turismo só entram em âmbito indireto).
nis2 profiles
nis2 profile camara_municipal -o out/camara
nis2 risk out/camara/entity.yaml out/camara/scenarios.yaml

# 1. Classificar a entidade e gerar o relatório de autoidentificação MyCiber
nis2 classify examples/entity_camara.yaml -o out/self_identification.md

# 1b. Aplicar a Matriz de Risco (Anexo II) a cenários de risco e apurar o nível
#     exigido (matriz + agregação do art. 30.º contra o tipo de entidade)
nis2 risk examples/entity_camara.yaml examples/scenarios_camara.yaml -o out/risk_matrix.md

# 2. Gerar um questionário de maturidade em branco para preencher
nis2 scaffold examples/entity_camara.yaml -o answers.yaml

# 3. Correr o assessment e gerar todos os deliverables (gap report, roadmap,
#    SoA, autoidentificação, plano de recolha de evidência, radar SVG,
#    relatório HTML imprimível com a marca do consultor, e o crosswalk dual
#    NIS2 ↔ ISO/IEC 27001/27002:2022 + checklist de documentos do SGSI).
#    Opcional: --risk <cenarios.yaml> deriva o nível da Matriz de Risco.
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

# 6b. Vista agregada da carteira de clientes (todos os snapshots gravados)
nis2 portfolio --history-dir out/.history -o out/carteira.md

# 7. Gerar a triagem de impacto significativo + o alerta inicial (24h) e o
#    relatório detalhado (72h) de um incidente para notificação ao CNCS via
#    MyCiber (Art. 23 DL 125/2025)
nis2 incident examples/entity_camara.yaml examples/incident_camara.yaml -o out/incidente

# 8. Gerar o calendário de obrigações da entidade a partir da data de
#    qualificação/notificação (lista de ativos art. 32.º, relatório anual, ...)
nis2 deadlines examples/entity_camara.yaml --since 2026-03-01 -o out/calendario.md

# 9. Agregar todos os deliverables Markdown da pasta num dossier HTML com a
#    marca do consultor (capa + índice), pronto a imprimir/guardar como PDF.
#    --pdf tenta exportar o PDF diretamente (weasyprint ou Chromium, se houver).
nis2 dossier out/ -o out/dossier.html --brand "Acme CyberSec" \
  --title "Relatório de Conformidade NIS2 — Câmara de Exemplo" --pdf
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
