# Multi-Jurisdiction Sanctions Coverage & Data-Quality Analysis — Case Study A

A reproducible analytical dataset, pipeline and dashboard for practising **sanctions-screening coverage analysis, cross-list data quality, and financial-crime data governance** across the four primary sanctions regimes — **OFAC SDN, EU FSF, the UK Sanctions List, and the UN Security Council Consolidated List**. Designed to be analysed in SQL, Python (pandas), Power BI or Tableau, and read as an intelligence brief.

> ℹ️ **Real where it counts, modelled where it must be — and labelled throughout.** Per-regime designation counts, update cadence and version strings are sourced live from **[OpenSanctions](https://www.opensanctions.org/datasets/sanctions/)** (`v.20260517074701-kjc`) and are independently citable. The entity-level cross-list resolution, data-quality flags and designation-velocity fields are **modelled and calibrated to those live marginals** — the exact entity-resolution join requires the licensed OpenSanctions bulk export. **No real designated-person names or PII are reproduced**; target keys are synthetic. Data © OpenSanctions Datenbanken GmbH, licensed **CC BY-NC 4.0**.

---

## Project overview

A fintech screening or financial-crime data-governance team needs to know:

1. **Are we screening the right lists?** (coverage)
2. **How good is the data inside them?** (quality)
3. **What would single-source screening miss?** (blind spots)
4. **Where is risk concentrated?** (jurisdictions, typologies, transliteration)
5. **Which programmes are moving fastest?** (velocity → refresh cadence)

This repository models the inputs to that workflow. It is sized for a portfolio — small enough to explain end-to-end in an interview, real enough that the analytical findings stand up to scrutiny.

---

## Data model

Four live regimes are consolidated by a deterministic pipeline into a single resolved analytical table at **unique-target grain**, where each list-membership column reconciles *exactly* to that regime's live target count:

```
OFAC SDN  (19,678) ┐
EU FSF     (5,900) ├─► build_case_study_a.py ─► consolidated_sanctions_4regime.csv  (24,183 rows × 18 cols)
UK List    (5,986) │                            analysis_stats.json                 (computed metrics)
UN SC        (999) ┘
        32,563 raw designation records  ─►  24,183 unique targets after resolution
```

| File | Rows | Grain |
|---|---:|---|
| `consolidated_sanctions_4regime.csv` | 24,183 | One row per unique designated target across the four regimes |
| `analysis_stats.json` | — | Pre-computed metrics (coverage, overlap, data-quality, velocity) emitted by the pipeline |

### Schema — `consolidated_sanctions_4regime.csv`

**Identity**
- `target_id` — synthetic stable key (`NK-000000`…). Not a real OpenSanctions identifier.

**List membership — drives coverage & overlap analysis**
- `on_ofac_sdn`, `on_eu_fsf`, `on_uk_fcdo`, `on_un_sc` — boolean; is the target designated on that regime's list
- `list_count` — integer 1–4; number of the four lists carrying the target
- `coverage_class` — `single-list` / `multi-list`
- `sole_list` — for single-list targets, which regime carries them; otherwise `multi`

**Classification**
- `schema` — entity type: Person / Organization / Vessel / CryptoWallet / Aircraft / Security
- `typology` — programme theme: Russia/Ukraine · Counter-terrorism · Narcotics/TCO/Trafficking · Iran/DPRK proliferation · Cyber · Human rights/Corruption · Other regional
- `country` — primary jurisdiction of risk
- `added_year` — year first designated (2018–2026); drives the velocity analysis

**Data-quality flags — drive the remediation / governance analysis**
- `dq_missing_dob`, `dq_name_translit`, `dq_mononym`, `dq_cross_source_conflict`, `dq_stale` — boolean defect flags
- `dq_any` — boolean; target carries ≥1 material defect

---

## What's in the data

The dataset is calibrated so the analytical patterns match the Case Study A findings:

- **32,563** raw designation records resolve to **24,183** unique targets
- **77.5%** of targets are single-list-only; **22.5%** appear on 2+ lists; **650** are on all four
- **Best-case single-list gap = 18.6%** — the share missed even by the largest list (OFAC SDN); UN-only screening misses **95.9%**
- **12.0%** of targets carry ≥1 data-quality defect — cross-source conflict (5.1%), transliteration risk (3.3%), missing DOB (2.8%), mononym (1.0%), stale record (0.4%)
- Entity-type mix: Person 12,072 · Organization 9,573 · Vessel 1,507 · CryptoWallet 702 · Aircraft 322 · Security 7
- Fastest-growing typologies (2022→2025): **Cyber +144%**, **Narcotics/TCO/Trafficking +103%**
- Transliteration risk concentrates on Russia, Iran, DPRK and other non-Latin-script jurisdictions

---

## How to use

```python
# Python (pandas)
import pandas as pd
df = pd.read_csv("consolidated_sanctions_4regime.csv")

df["coverage_class"].value_counts(normalize=True)      # single- vs multi-list share
1 - df["on_ofac_sdn"].mean()                           # best single-list coverage gap (~0.186)
df.groupby("schema")["dq_any"].mean().mul(100).round(1)# data-quality defect rate by entity type
```

```sql
-- SQL (SQLite / Postgres / BigQuery — CSV-loadable)
-- Single-list blind spots: how much of the universe sits on exactly one list?
SELECT coverage_class,
       COUNT(*)                                          AS targets,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM consolidated_sanctions_4regime
GROUP BY coverage_class;

-- Remediation backlog: defect rate by programme typology
SELECT typology,
       ROUND(100.0 * AVG(CASE WHEN dq_any THEN 1 ELSE 0 END), 1) AS defect_rate_pct
FROM consolidated_sanctions_4regime
GROUP BY typology
ORDER BY defect_rate_pct DESC;
```

Load `consolidated_sanctions_4regime.csv` into Power BI / Tableau and slice by `coverage_class`, `typology`, `country`, `added_year`, and the `dq_*` flags. The boolean `on_*` columns drive coverage and overlap visuals directly.

---

## Reproduce

```bash
pip install -r requirements.txt
python build_case_study_a.py      # regenerates consolidated_sanctions_4regime.csv + analysis_stats.json
```

The pipeline is deterministic (fixed random seed), so a re-run reproduces the dataset and every figure above exactly.

---

## Methodology note

Per-regime target counts, entity-type splits, programme taxonomies, update cadence and version strings are sourced live from the OpenSanctions Consolidated Sanctions catalogue (May 2026) and are individually citable. The cross-list **resolution** layer (which targets sit on more than one list), the **data-quality** defect incidence, and the designation-**velocity** series are modelled — calibrated to the live marginals and to documented OpenSanctions resolution behaviour, and reported as planning estimates rather than a measured join. The build is seeded and regenerable. No real designated-entity names or PII are reproduced. Data © OpenSanctions Datenbanken GmbH, licensed CC BY-NC 4.0; commercial use of the underlying sanctions data requires a licence from OpenSanctions.

---

## Companion artefacts (included in this repo)

- `Sanctions_Intelligence_Dashboard.html` — interactive Chart.js / Grid.js dashboard (coverage, overlap, velocity, data-quality, jurisdictions, entity-type mix)
- `Sanctions_Intelligence_Report.html` — narrative intelligence report version of the same analysis
- `build_case_study_a.py` — the reproducible pipeline that builds the dataset

## About

Part of a financial-intelligence portfolio by **Bukola Apampa** (Financial Intelligence Research Analyst) demonstrating sanctions-screening coverage analysis, cross-list data quality and AML/financial-crime data governance in SQL, Python and Power BI. Companion to `pep-screening-governance-synth`.

**Suggested topics:** `portfolio` · `sql` · `power-bi` · `pandas` · `data-quality` · `aml` · `sanctions` · `financial-crime` · `data-governance` · `opensanctions`



