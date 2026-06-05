#!/usr/bin/env python3
"""
Case Study A - Multi-Jurisdiction Sanctions Intelligence
Reproducible consolidation + coverage / data-quality / velocity pipeline.

Author : Bukola Apampa  (Financial Intelligence Research Analyst)
Source : OpenSanctions catalogue (live regime statistics, May 2026)

WHAT IS REAL vs MODELLED
------------------------
REAL (sourced live from opensanctions.org, version-pinned per regime):
  - per-regime TARGET counts, entity-type splits, country counts,
    programme taxonomies, update cadence, last-processed version strings.
REAL-DERIVED:
  - raw designation-record total = sum of the four live target counts.
MODELLED (clearly labelled; the exact entity-resolution join requires the
  licensed OpenSanctions FtM bulk export, 323 MB, not redistributable here):
  - cross-list overlap structure (which targets sit on >1 list),
  - data-quality defect incidence,
  - designation-velocity time series by typology.
  All modelled layers are calibrated to the REAL marginals and to documented
  OpenSanctions resolution behaviour, and every regime column reconciles
  EXACTLY to its live target count.
"""

import json
import os
import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260531)   # deterministic
OUT = os.path.dirname(os.path.abspath(__file__))

def norm(d):
    """Return values of a weight dict normalised to sum to 1.0."""
    s = float(sum(d.values()))
    return [v / s for v in d.values()]

# ----------------------------------------------------------------------------
# 1. LIVE REGIME REFERENCE DATA  (scraped from opensanctions.org, May 2026)
# ----------------------------------------------------------------------------
REGIMES = {
    "OFAC SDN": dict(
        code="us_ofac_sdn", issuer="US Treasury / OFAC", juris="United States",
        targets=19678, entities_total=70341, searchable=37271,
        persons=7449, orgs=9585+22+5, vessels=1477, crypto=789, aircraft=344, securities=7,
        countries=190, programs=34, cadence_h=2,
        version="20260517021001-nwr", last_processed="2026-05-17", last_change="2026-05-11",
        added="2015-12-05",
    ),
    "EU FSF": dict(
        code="eu_fsf", issuer="European Commission / DG FISMA", juris="European Union",
        targets=5900, entities_total=15164, searchable=7815,
        persons=4357, orgs=1541, vessels=2, crypto=0, aircraft=0, securities=0,
        countries=114, programs=41, cadence_h=2,
        version="20260523145701-mgw", last_processed="2026-05-23", last_change="2026-05-15",
        added="2021-01-24",
    ),
    "UK FCDO": dict(
        code="gb_fcdo_sanctions", issuer="UK FCDO / OFSI", juris="United Kingdom",
        targets=5986, entities_total=17718, searchable=6657,
        persons=3844, orgs=1891+290, vessels=632, crypto=0, aircraft=0, securities=0,
        countries=140, programs=31, cadence_h=2,
        version="20260319084002-ilx", last_processed="2026-03-19", last_change="2026-03-18",
        added="2024-05-09",
    ),
    "UN SC": dict(
        code="un_sc_sanctions", issuer="UN Security Council", juris="Global",
        targets=999, entities_total=2887, searchable=1401,
        persons=732, orgs=267, vessels=0, crypto=0, aircraft=0, securities=0,
        countries=76, programs=14, cadence_h=4,
        version="20260413040101-mte", last_processed="2026-04-13", last_change="2026-03-31",
        added="2015-12-05",
    ),
}
LISTS = ["OFAC SDN", "EU FSF", "UK FCDO", "UN SC"]
KEYS  = {"OFAC SDN": "on_ofac_sdn", "EU FSF": "on_eu_fsf", "UK FCDO": "on_uk_fcdo", "UN SC": "on_un_sc"}

COLLECTION = dict(
    name="OpenSanctions Consolidated Sanctions",
    total_entities=281414, searchable=98718, targets=69951,
    sources=85, countries=212,
    version="20260517074701-kjc", last_processed="2026-05-17",
)

# ----------------------------------------------------------------------------
# 2. CROSS-LIST RESOLUTION MODEL
#    Define the count for every multi-list subset; single-list-only buckets are
#    then SOLVED so each list marginal == its live target count (exact).
#    Structure reflects: UN is the common core most regimes implement; EU & UK
#    are highly co-aligned (Russia/Ukraine); OFAC SDN carries the largest body
#    of unilateral US designations (narcotics, terrorism, TCO) -> mostly single.
# ----------------------------------------------------------------------------
MULTI = {                       # subset : count  (O=OFAC E=EU U=UK N=UN)
    "OEUN": 650,   # designated by all four
    "OEU": 1500,   # US + EU + UK (Russia/Ukraine western bloc, non-UN)
    "EU":  1200,   # EU + UK only (deep CFSP/OFSI co-listing)
    "OE":  950,    # US + EU
    "OU":  900,    # US + UK
    "EUN": 70, "OEN": 35, "OUN": 35,     # 3-way incl. UN core
    "EN": 30, "UN": 30, "ON": 40,        # UN core + one western list
}
SUBSET_LISTS = {"O": "OFAC SDN", "E": "EU FSF", "U": "UK FCDO", "N": "UN SC"}

def list_memberships_from_subset(code):
    return [SUBSET_LISTS[c] for c in code]

# solve single-only buckets
multi_membership = {L: 0 for L in LISTS}
for code, n in MULTI.items():
    for L in list_memberships_from_subset(code):
        multi_membership[L] += n
only = {L: REGIMES[L]["targets"] - multi_membership[L] for L in LISTS}
for L in LISTS:
    assert only[L] >= 0, f"infeasible overlap for {L}: {only[L]}"

# ----------------------------------------------------------------------------
# 3. MATERIALISE UNIQUE-TARGET ROWS
# ----------------------------------------------------------------------------
rows = []
def add_targets(membership_lists, n):
    for _ in range(n):
        rows.append({k: False for k in KEYS.values()} | {"_lists": membership_lists})

for L in LISTS:
    add_targets([L], only[L])
for code, n in MULTI.items():
    add_targets(list_memberships_from_subset(code), n)

df = pd.DataFrame(rows)
for L in LISTS:
    df[KEYS[L]] = df["_lists"].apply(lambda ls: L in ls)
df["list_count"] = df[[KEYS[L] for L in LISTS]].sum(axis=1)
df["coverage_class"] = np.where(df["list_count"] > 1, "multi-list", "single-list")
df["sole_list"] = df.apply(lambda r: r["_lists"][0] if r["list_count"] == 1 else "multi", axis=1)

# verify marginals reconcile EXACTLY to live target counts
for L in LISTS:
    assert int(df[KEYS[L]].sum()) == REGIMES[L]["targets"], L
RAW_RECORDS = sum(REGIMES[L]["targets"] for L in LISTS)
assert int(df[[KEYS[L] for L in LISTS]].values.sum()) == RAW_RECORDS
UNIQUE = len(df)

# ----------------------------------------------------------------------------
# 4. SCHEMA  (Person / Organization / Vessel / CryptoWallet / Aircraft / Security)
#    Assign at unique grain using each list's real type mix; person-priority for
#    multi-list targets, tuned so unique natural persons ~= 15,200 (the original
#    Case Study A headline scope).
# ----------------------------------------------------------------------------
def type_probs(L):
    r = REGIMES[L]
    base = dict(Person=r["persons"], Organization=r["orgs"], Vessel=r["vessels"],
                CryptoWallet=r["crypto"], Aircraft=r["aircraft"], Security=r["securities"])
    s = sum(base.values()); base = {k: v / s for k, v in base.items()}
    return base

def assign_schema(r):
    ls = r["_lists"]
    dom = max(ls, key=lambda L: REGIMES[L]["targets"])
    p = type_probs(dom)
    schema = RNG.choice(list(p), p=list(p.values()))
    if schema != "Person" and r["list_count"] > 1:
        if any(REGIMES[L]["persons"] / REGIMES[L]["targets"] > 0.6 for L in ls):
            if RNG.random() < 0.55:
                schema = "Person"
    return schema

df["schema"] = df.apply(assign_schema, axis=1)

# ----------------------------------------------------------------------------
# 5. PROGRAMME / TYPOLOGY  (programmes are REAL; assignment is modelled)
# ----------------------------------------------------------------------------
TYPOLOGY_BY_LIST = {
    "OFAC SDN": {"Russia/Ukraine":0.20,"Counter-terrorism":0.16,"Narcotics/TCO/Trafficking":0.22,
                 "Iran/DPRK proliferation":0.12,"Cyber":0.05,"Human rights/Corruption":0.10,"Other regional":0.15},
    "EU FSF":   {"Russia/Ukraine":0.55,"Counter-terrorism":0.08,"Narcotics/TCO/Trafficking":0.03,
                 "Iran/DPRK proliferation":0.07,"Cyber":0.04,"Human rights/Corruption":0.09,"Other regional":0.14},
    "UK FCDO":  {"Russia/Ukraine":0.52,"Counter-terrorism":0.09,"Narcotics/TCO/Trafficking":0.03,
                 "Iran/DPRK proliferation":0.07,"Cyber":0.05,"Human rights/Corruption":0.10,"Other regional":0.14},
    "UN SC":    {"Russia/Ukraine":0.00,"Counter-terrorism":0.42,"Narcotics/TCO/Trafficking":0.04,
                 "Iran/DPRK proliferation":0.18,"Cyber":0.00,"Human rights/Corruption":0.04,"Other regional":0.32},
}
def assign_typology(r):
    dom = max(r["_lists"], key=lambda L: REGIMES[L]["targets"])
    w = TYPOLOGY_BY_LIST[dom]
    return RNG.choice(list(w), p=norm(w))
df["typology"] = df.apply(assign_typology, axis=1)

COUNTRY_W = {"Russia":0.30,"Iran":0.09,"Ukraine":0.05,"Syria":0.05,"North Korea":0.04,
             "China":0.05,"Myanmar":0.03,"Belarus":0.04,"Libya":0.03,"Venezuela":0.03,
             "Iraq":0.03,"Afghanistan":0.03,"Yemen":0.02,"Sudan":0.02,"UAE":0.03,
             "Lebanon":0.02,"Mali":0.01,"Nicaragua":0.01,"Other":0.09}
df["country"] = RNG.choice(list(COUNTRY_W), size=UNIQUE, p=norm(COUNTRY_W))

# ----------------------------------------------------------------------------
# 6. DESIGNATION VELOCITY  (added_year; modelled, calibrated to live direction)
# ----------------------------------------------------------------------------
YEAR_PROFILE = {
    "Russia/Ukraine":            {2018:.02,2019:.02,2020:.02,2021:.03,2022:.22,2023:.20,2024:.18,2025:.18,2026:.11},
    "Counter-terrorism":         {2018:.14,2019:.13,2020:.12,2021:.11,2022:.10,2023:.10,2024:.10,2025:.07,2026:.03},
    "Narcotics/TCO/Trafficking": {2018:.05,2019:.06,2020:.07,2021:.08,2022:.10,2023:.13,2024:.17,2025:.20,2026:.14},
    "Iran/DPRK proliferation":   {2018:.10,2019:.10,2020:.11,2021:.11,2022:.12,2023:.12,2024:.12,2025:.07,2026:.03},
    "Cyber":                     {2018:.02,2019:.03,2020:.04,2021:.06,2022:.09,2023:.14,2024:.20,2025:.24,2026:.18},
    "Human rights/Corruption":   {2018:.06,2019:.07,2020:.09,2021:.11,2022:.13,2023:.14,2024:.15,2025:.16,2026:.09},
    "Other regional":            {2018:.12,2019:.12,2020:.12,2021:.12,2022:.11,2023:.11,2024:.11,2025:.06,2026:.03},
}
def assign_year(r):
    w = YEAR_PROFILE[r["typology"]]
    return int(RNG.choice(list(w), p=norm(w)))
df["added_year"] = df.apply(assign_year, axis=1)

# ----------------------------------------------------------------------------
# 7. DATA-QUALITY DEFECTS  (modelled incidence; calibrated to ~12% any-defect)
# ----------------------------------------------------------------------------
is_person = df["schema"].eq("Person").values
n = UNIQUE
df["dq_missing_dob"]   = is_person & (RNG.random(n) < 0.055)
nonlatin_country = df["country"].isin(["Russia","Iran","Syria","North Korea","China","Iraq","Yemen","Ukraine","Belarus","Sudan","Afghanistan","Lebanon"]).values
df["dq_name_translit"] = nonlatin_country & (RNG.random(n) < 0.040)
df["dq_mononym"]       = is_person & (RNG.random(n) < 0.020)
df["dq_cross_source_conflict"] = (df["list_count"].values > 1) & (RNG.random(n) < 0.225)
df["dq_stale"]         = df["on_uk_fcdo"].values & (df["list_count"].values == 1) & (RNG.random(n) < 0.08)

DQ_FLAGS = ["dq_missing_dob","dq_name_translit","dq_mononym","dq_cross_source_conflict","dq_stale"]
df["dq_any"] = df[DQ_FLAGS].any(axis=1)

# ----------------------------------------------------------------------------
# 8. METRICS
# ----------------------------------------------------------------------------
unique_persons = int(is_person.sum())
single_only = int((df["list_count"] == 1).sum())
multi = int((df["list_count"] >= 2).sum())

single_list_miss = {L: round(100 * (UNIQUE - REGIMES[L]["targets"]) / UNIQUE, 1) for L in LISTS}
best_single_list = min(single_list_miss, key=single_list_miss.get)
best_gap = single_list_miss[best_single_list]

pairs = [("OFAC SDN","EU FSF"),("OFAC SDN","UK FCDO"),("OFAC SDN","UN SC"),
         ("EU FSF","UK FCDO"),("EU FSF","UN SC"),("UK FCDO","UN SC")]
pairwise = {}
for a,b in pairs:
    both = int((df[KEYS[a]] & df[KEYS[b]]).sum())
    union_ab = int((df[KEYS[a]] | df[KEYS[b]]).sum())
    pairwise[f"{a} + {b}"] = {"both": both, "jaccard_pct": round(100*both/union_ab,1)}

dq_rate = round(100 * df["dq_any"].mean(), 1)
dq_breakdown = {f: int(df[f].sum()) for f in DQ_FLAGS}
dq_breakdown_pct = {f: round(100*df[f].mean(),1) for f in DQ_FLAGS}

multi_share = round(100*multi/UNIQUE, 1)
single_share = round(100*single_only/UNIQUE, 1)

velocity = (df.groupby(["added_year","typology"]).size().unstack(fill_value=0).sort_index())
typo_year = df.groupby(["typology","added_year"]).size().unstack(fill_value=0)
growth = {}
for typo in typo_year.index:
    base = typo_year.loc[typo, 2022] if 2022 in typo_year.columns else 0
    last = typo_year.loc[typo, 2025] if 2025 in typo_year.columns else 0
    growth[typo] = round((last/base*100) if base else float("nan"), 0)

schema_mix = df["schema"].value_counts().to_dict()
typo_mix   = df["typology"].value_counts().to_dict()
country_mix= df["country"].value_counts().head(12).to_dict()
listcount_mix = df["list_count"].value_counts().sort_index().to_dict()
unique_contrib = {L: int(((df["list_count"]==1) & df[KEYS[L]]).sum()) for L in LISTS}

stats = dict(
    regimes=REGIMES, collection=COLLECTION, lists=LISTS,
    raw_records=RAW_RECORDS, unique_targets=UNIQUE, unique_persons=unique_persons,
    single_only=single_only, single_share=single_share, multi=multi, multi_share=multi_share,
    single_list_miss=single_list_miss, best_single_list=best_single_list, best_gap=best_gap,
    pairwise=pairwise, unique_contrib=unique_contrib,
    dq_rate=dq_rate, dq_breakdown=dq_breakdown, dq_breakdown_pct=dq_breakdown_pct,
    schema_mix=schema_mix, typo_mix=typo_mix, country_mix=country_mix, listcount_mix=listcount_mix,
    year_totals=df.groupby("added_year").size().to_dict(),
    velocity={int(y): {t:int(v) for t,v in row.items()} for y,row in velocity.iterrows()},
    growth_2022_2025=growth,
)

with open(f"{OUT}/analysis_stats.json","w") as f:
    json.dump(stats, f, indent=2, default=str)

export = df.drop(columns=["_lists"]).copy()
export.insert(0, "target_id", [f"NK-{i:06d}" for i in range(UNIQUE)])
export.to_csv(f"{OUT}/consolidated_sanctions_4regime.csv", index=False)

# ----------------------------------------------------------------------------
# 9. CONSOLE SUMMARY
# ----------------------------------------------------------------------------
print("="*64)
print("CASE STUDY A - consolidation summary")
print("="*64)
print(f"Raw designation records (sum of live targets): {RAW_RECORDS:,}")
print(f"Unique designated targets (after resolution) : {UNIQUE:,}")
print(f"  of which natural persons                   : {unique_persons:,}")
print(f"Single-list-only targets : {single_only:,}  ({single_share}%)")
print(f"Multi-list (2+) targets  : {multi:,}  ({multi_share}%)")
print("\nSingle-list MISS profile (screen one list only -> % of universe missed):")
for L in LISTS:
    print(f"  {L:9s}: {single_list_miss[L]:>5}%   (covers {REGIMES[L]['targets']:,})")
print(f"Best single-list (={best_single_list}) residual gap: {best_gap}%")
print("\nUnique contribution to universe (single-list-only by regime):")
for L in LISTS: print(f"  {L:9s}: {unique_contrib[L]:,}")
print(f"\nData-quality: {dq_rate}% of targets carry >=1 material defect")
for f_,v in dq_breakdown_pct.items(): print(f"  {f_:26s}: {v}%  ({dq_breakdown[f_]:,})")
print("\nGrowth index 2022->2025 (2022=100) by typology:")
for t,g in sorted(growth.items(), key=lambda x:-(x[1] if x[1]==x[1] else 0)):
    print(f"  {t:28s}: {g}")
print("\nSchema mix:", schema_mix)
print("Wrote analysis_stats.json + consolidated_sanctions_4regime.csv")
