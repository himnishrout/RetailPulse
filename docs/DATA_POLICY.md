# Data contract

Grain: one retained source invoice/product line, not one invoice. An order is DISTINCT invoice on positive purchase lines. Country is the transaction country; the customer dimension uses latest observed country. Dates are source-naive timestamps. Prices are GBP per UCI. This is historical giftware retail with wholesale buyers, not a current general ecommerce population.

Missing/invalid customer IDs: preserve anonymous sales for revenue and product analysis; exclude from RFM, cohorts, labels, and predictions. Do not impute identities: this would fabricate repeat behavior. Cohort/customer metrics therefore describe the identified purchasing population only. Invoice customer conflicts fail the run.

Exact duplicate policy: keep the first line across all 8 business fields, ignoring sheet/row provenance. Identical legitimate lines are possible; report the removed count and compare totals with raw data. All original rows remain in PostgreSQL staging. Never deduplicate merely by invoice and SKU: an invoice can contain repeated product lines.

Invalid date/invoice/SKU, nonfinite quantity/price, quantity zero/fractional, or nonpositive price: quarantine. Missing description and country are retained. Positive quantities on C-prefixed invoices are quarantined. Customer IDs must be positive integers; invalid ones become anonymous. Negative quantities with positive prices are kept as credits, even without C prefixes; distinguish the prefix flag from the negative-quantity flag.

Gross sales = positive line values; return credit value = absolute negative line values; net revenue = gross minus credits. Net is not profit. AOV = gross sales / distinct purchase invoices. Return value ratio = credits / gross sales over the selected window. It is not a matched product return probability, and may exceed 100% when returns refer to earlier sales. Return/cancellation reasons and exact original-sale matches are not available. Do not call all negative records confirmed cancellations.

Extreme positive prices/quantities are retained rather than silently clipped: wholesale orders may be legitimate. Inspect top lines and report sensitivity before claiming robustness. The package does not infer tax, margin, discounts, marketing response, or cancellation causes.

RFM uses known positive purchases through the final snapshot; monetary is gross spend. Scores use tied percentile ranks and explicit segment rules. Scores are descriptive, not discovered natural clusters. Final RFM must never be merged into historical ML features: that would leak future data.

Cohorts are based on FIRST OBSERVED purchase; customers may have purchased before the dataset began. Retention means active in that offset calendar month, not survival or purchase within 90 days. Zero-activity fully observed cells are zero, future cells are absent, the last calendar month is conservatively censored. The first cohort month may have truncated history. Segment filters describe the end-of-history segment, not the segment at the transaction date.

Monthly endpoints are marked potentially partial; compare complete months and same-month prior year before interpreting seasonality as growth. Order/AOV decomposition applies to gross sales; net changes also include return-credit changes. Customer purchasing history and return lines are never taken from after a prediction snapshot.
