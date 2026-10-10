# Evaluation you can defend in an interview

Run `python pipeline.py --input data/uci.zip`. Metrics are actual run outputs in `outputs/evaluation.json` and `outputs/RESULTS.md`; never copy an assumed score. The input SHA256 is recorded in data_quality.json. Record your Python/package versions with `python -m pip freeze > outputs/environment.txt`.

Eligibility: every identified customer with at least one valid positive purchase before a snapshot, including inactive customers. Features use all earlier purchases, with 30/90-day windows. Target is ANY valid positive purchase in [snapshot, snapshot+90 days). Returns alone do not make the target positive; a later return does not retrospectively remove a purchase.

Temporal design: derive the test date 90 days before the last observed date's midnight, leaving a full 90-day future. Validation is 91 days earlier, training is another 91 days earlier. At least 180 days of history precede training. Training labels finish before validation features; validation labels finish before test features. No random transaction split. The same customers may recur: this tests the existing-customer use case. Training and test purchase histories have different lengths, a distribution-shift limitation.

Train Logistic Regression (scaled numeric features) and HistGradientBoosting on the training snapshot. Select by validation average precision ONLY. Do not choose the winner based on test performance. The selected fitted model is not refitted before test, making the audited result reproducible. Final historical scores apply that model at the dataset end; those scores have no observable future labels and are not live forecasts of today's customers.

Baselines:
- Constant probability equal to training repeat rate: no behavior signal. Constant AP equals test prevalence.
- Recency: exp(-recency/90), monotonic in how recently someone purchased. This is a ranking rule, not a calibrated probability model.

Metrics:
- Average precision (AP): primary ranking metric; this implementation is sklearn average_precision_score, not trapezoidal area under a plotted PR curve. Higher is better; report prevalence alongside it.
- ROC-AUC: general ranking separation, supplementary.
- Precision@top10%: observed repeat rate among the ceil(10% * customer count) highest scores, fixed before test. Ties use stable row order; the constant baseline's top subset has no business meaning.
- Lift@top10%: that rate divided by overall repeat rate. This is predictive concentration, NOT campaign revenue uplift.
- Brier: mean squared probability error (lower is better); compare to constant baseline and inspect calibration.csv. No calibrated-model claim without checking reliability.
- Precision/recall/F1/confusion matrix: fixed probability threshold 0.5, descriptive only; not a business-optimal threshold.

The run bootstraps paired test customers 500 times (seed 42), producing a 95% percentile interval for model AP minus recency AP. If it includes zero, avoid claiming reliable superiority. It conditions on one date and fitted model; it does not capture seasonal drift, retraining uncertainty, or independent future replications. Test once, freeze findings; tuning against test invalidates the holdout.

Business interpretation: high repeat scores identify likely buyers, not customers persuaded by a campaign. Low scores alone do not identify profitable reactivation targets. A campaign should use an experiment with randomized treatment/control, revenue net of returns, cost, margin and unsubscribe outcomes. None of that uplift is measured here.

Analytics verification: raw = retained + excluded; gross - credits = net; distinct invoices prevent line-level order double counting; cohort zeroes and censoring checked by tests. Compare SQL outputs to CSV totals after DB load. Check cohort sizes/anonymous share and plot order-frequency/recency distributions before judging data suitable. See data_quality.json for measured repeat share.

Resume: use the generated wording in RESULTS.md after review. Add Power BI only after you assemble and verify the report. If ML loses to recency, report the finding honestly: 'Benchmarked 90-day repeat-purchase models against a recency baseline using temporal validation.' Do not claim revenue improvements or production deployment.
