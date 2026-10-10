# RetailPulse measured run

Input SHA256: 572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb

Processed 1,067,371 raw lines; retained 1,027,016; identified 5,878 purchasing customers. Repeat-customer share over the complete historical window: 72.4%.

Selected gradient_boosting on validation AP. Test: 5,281 customers; positive rate 43.4%; AP 0.761 versus recency AP 0.686; ROC-AUC 0.787; Brier 0.197; precision@top10% 91.9%; lift@top10% 2.12x.

Resume candidate (use only after reviewing evaluation): Built a retail analytics pipeline over 1,067,371 transaction lines and evaluated 90-day repeat-purchase predictions on 5,281 temporally held-out customers, achieving AP 0.761 versus a recency baseline of 0.686.

Power BI report must be assembled separately. No campaign revenue improvement was measured. See docs/EVALUATION.md for scope and limitations.
