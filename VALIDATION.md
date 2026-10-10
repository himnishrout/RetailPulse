# Validation status

Real UCI Online Retail II workbook downloaded and both sheets read. Python analytics and ML pipeline executed end to end on the real dataset. Five semantic tests passed: data reconciliation, feature leakage, horizon end boundary, cohort zero/censoring, and anonymous identity exclusion. Python compile check passed.

PostgreSQL DDL/loading and Power BI report/DAX were not executed: PostgreSQL, Docker and Power BI Desktop are not installed in this execution environment. Run README commands on your Mac, then follow docs/POWER_BI.md and its acceptance checklist. No PBIX is supplied or claimed.

The ZIP contains measured outputs (including real Power BI input CSVs) but excludes the source workbook/ZIP. Redownload it to reproduce. Source SHA256 is in outputs/data_quality.json.

Run environment:
- pandas: 2.2.3
- numpy: 2.3.5
- scikit-learn: 1.8.0
- openpyxl: 3.1.5
- joblib: 1.5.3

Real-output reconciliation passed: gross £20,476,260.43 minus credits £1,462,424.18 equals net £19,013,836.25; monthly totals agree; scores cover the purchasing customer dimension.
