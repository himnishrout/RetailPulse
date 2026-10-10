# Power BI on your Mac: choose an access route

Power BI Desktop is a Windows application, not a native macOS app. Recommendation: keep Python/PostgreSQL on the Mac, then use a Windows PC (college/lab/borrowed computer or a remote Windows desktop) for the final PBIX. Import the generated CSVs: remote Windows localhost is NOT your Mac database. This avoids exposing PostgreSQL or depending on a gateway for this static portfolio dataset.

Microsoft documents Windows 10/Server 2016 or later and currently a required Windows-on-ARM update. Microsoft explicitly supports full desktop virtualization through Azure Virtual Desktop and Windows 365. A local Windows VM is another practical possibility but needs Windows, memory and disk space and should be tested before buying anything. For an 8 GB Mac, a remote/borrowed Windows computer is the better first step than running Docker and a Windows VM together.

Browser route (no Windows): visit https://app.powerbi.com with a permitted work/school account, potentially your university account. Signup and features depend on tenant policy/license; having a university email is not a guarantee. Create a workspace/My workspace semantic model from CSV and create a report. Current Microsoft instructions: New item → Semantic model → CSV → Upload file → Next → preview → Create a report. Sharing/licensing is separate from local report building.

Upload outputs/sales_explorer.csv for sales/product analysis, dim_customers.csv for customer segmentation, cohort_retention.csv for the retention matrix, customer_scores.csv for predictions, and data_quality.csv for the audit. Each CSV can form a separate browser report. Multiple tables/relationships and custom measures in one report depend on available model editing; do not assume five independent CSV imports automatically form one semantic model. If those controls are unavailable, use the standalone reports initially and finish the unified model in Desktop. There is no completed browser report or PBIX in this package.

Official sources checked October 2026:
- https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop
- https://learn.microsoft.com/en-us/power-bi/connect-data/service-comma-separated-value-files
- https://learn.microsoft.com/en-us/power-bi/fundamentals/service-self-service-signup-purchase-for-power-bi
- https://learn.microsoft.com/en-us/power-query/connectors/postgresql

## Desktop: load and configure

1. Get Data → Text/CSV → import fct_transactions, dim_customers, dim_products, dim_dates, cohort_retention, customer_scores, data_quality. Use the CSV filename stem as table name. Choose UTF-8; invoice/product/customer keys should be Text in every table, preserving blanks as null, not 'nan'. Quantity/score counts: Whole number; amounts/probabilities: Decimal; date: Date; invoice_date: Date/Time; flags: True/False.
2. Turn off automatic relationship detection / remove generated relationships before adding the explicit relationships below. Mark dim_dates as the date table using date. Sort month by chronological YYYY-MM text. Disable auto date/time for this file.
3. Relationships (single-direction from dimension to detail): dim_dates[date] 1:* fct_transactions[date]; dim_products[product_id] 1:* facts[product_id]; dim_customers[customer_id] 1:* facts[customer_id]; dim_customers[customer_id] 1:* customer_scores[customer_id]. Do not use bidirectional filters. Keep cohorts and data_quality disconnected. Do not connect snapshot dates to transaction dates.
4. Country slicer on transaction pages uses fct_transactions[country]. Segment slicer uses dim_customers[segment]. Note: segment is the FINAL historical segment, not as-of transaction segmentation; country/transaction date/product filters intentionally do not affect the fixed historical score/cohort pages. Label page scope visibly.
5. Anonymous and return-only customers have unmatched dimension IDs: keep the blank group if reconciling all revenue. A segment filter reduces totals to matched purchasing customers. Do not hide blank customers globally.
6. Import powerbi_theme.json in View → Themes → Browse for themes. 16:9 pages, cards along the top, two primary charts below, consistent GBP and percent formats.

Optional direct DB connection: Get Data → PostgreSQL → server localhost:5432, database retailpulse → Import → credentials → select retailpulse tables. Only use localhost if Windows can actually reach that DB locally or through an explicitly configured tunnel. CSV import is easiest across computers. For a static historical report, refresh after rerunning Python. Scheduled service refresh against a Mac-local database requires a reachable source and suitable gateway/cloud setup; it is not supplied.

## Exact measures

Create the measures in measures.dax individually (not the entire file as one formula). Gross/AOV use purchase lines, net includes return credits. Use dim_dates[month] on time charts. Monthly growth may be blank for the first month; endpoint months are incomplete and should not be presented as comparable full months.

## Five report pages

| Page | Visual | Fields / configuration |
|---|---|---|
| Business overview | Cards | Gross Sales, Return Credits, Net Revenue, Purchase Orders, AOV, Active Identified Customers |
| Business overview | Line chart | X dim_dates[month], Y Net Revenue; sort ascending; tooltips Gross Sales, Return Credits, Purchase Orders, AOV |
| Business overview | Clustered columns | X facts[country], Y Net Revenue; sort descending, Top 10 countries by Net Revenue |
| Business overview | Slicers | date range, facts[country], product dimension, final customer segment |
| Customer retention | Matrix | Rows cohort_retention[cohort], columns month_index, values Retention; percent 1 decimal; conditional background gradient; disable grand totals; keep censored blanks blank |
| Customer retention | Bar | X Count of dim_customers[customer_id], Y segment; label 'final observed RFM snapshot' |
| Customer retention | Table | customer_id, orders, spend, recency_days, segment; spend descending; no summed recency/score totals |
| Products and credits | Bar | product description, Gross Sales; top 15 by Gross Sales |
| Products and credits | Scatter | product_id detail, X Gross Sales, Y Return Value Ratio, size Return Credits; minimum gross sales £100 filter; tooltip sale quantity/credits |
| Products and credits | Table | product_id, description, Gross Sales, Return Credits, Return Value Ratio; label ratios as unmatched credits/sales |
| Predictions and actions | Table | customer_scores customer_id, repeat_probability, recency_days, orders, spend; sort probability descending; percent 1 decimal; label exact historical snapshot |
| Predictions and actions | Histogram | create probability bins of 0.1; X bin, Y count customer_id |
| Predictions and actions | Calibration line | import calibration.csv separately; X mean_predicted_probability, Y observed_repeat_rate; numeric axes 0–1; label held-out test, not current scores |
| Predictions and actions | Text | 'Scores predict purchase, not campaign response. Test campaigns with randomized controls.' Include evaluated AP, recency AP, top10 precision and test date |
| Data quality | Table | data_quality check and value, no summed totals; raw/retained/excluded/anonymous counts |
| Data quality | Text | Explain deduplication policy, anonymous retention exclusions, negative credits, and partial months |

For browser sales_explorer: sum gross_sales / return_credit / line_revenue for the cards and charts. Orders must use DISTINCT COUNT purchase_invoice EXCLUDING BLANK, not sum or count of rows. If the browser cannot create that measure, show orders and AOV from monthly_sales.csv as another standalone report. Do not use SUM of order/customer counts across product groups.

## Acceptance checklist before resume / screenshots

- All-date unfiltered gross minus credits equals net, matching Python/SQL. Purchase Orders equals count of distinct positive purchase invoices.
- Country/date/product slicers change transaction visuals; fixed cohort and scoring visuals are clearly scoped and do not misleadingly inherit those filters.
- Missing customer rows contribute to overall sales; identified retention excludes them.
- Cohort rows start at 100% for complete month zero; zero later activity remains zero, final partial month is blank.
- Snapshot scores are dated 2011 and never called live 2026 probabilities.
- Test metrics match evaluation.json; top10 lift never called campaign uplift.
- Power BI DAX/report still needs user validation; formulas were supplied, not executed in a Power BI engine here.
