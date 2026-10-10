-- Diagnostic candidates only: deletion of staging rows is never automatic.
WITH ranked AS (
 SELECT *, row_number() OVER (
 PARTITION BY invoice,product_id,description,quantity,invoice_date,unit_price,customer_id,country
 ORDER BY source_sheet,source_row) AS duplicate_rank
 FROM retailpulse.stg_transactions
) SELECT * FROM ranked WHERE duplicate_rank>1;

SELECT count(*) AS total_rows,
 count(*) FILTER (WHERE customer_id IS NULL) AS missing_customer_rows,
 count(*) FILTER (WHERE unit_price<=0) AS nonpositive_price_rows,
 count(*) FILTER (WHERE quantity<0) AS negative_quantity_rows,
 count(*) FILTER (WHERE upper(invoice) LIKE 'C%' AND quantity>0) AS inconsistent_cancellations
FROM retailpulse.stg_transactions;

-- Full outer month spine comes from dim_dates, so zero-sales months are not hidden.
WITH months AS (SELECT DISTINCT month FROM retailpulse.dim_dates),
 revenue AS (
 SELECT to_char(invoice_date,'YYYY-MM') AS month,
 sum(line_revenue) AS net_revenue,
 sum(line_revenue) FILTER(WHERE is_sale) AS gross_sales,
 count(DISTINCT invoice) FILTER(WHERE is_sale) AS orders
 FROM retailpulse.fct_transactions GROUP BY 1
), combined AS (
 SELECT m.month,coalesce(r.net_revenue,0) AS net_revenue,
 coalesce(r.gross_sales,0) AS gross_sales,coalesce(r.orders,0) AS orders
 FROM months m LEFT JOIN revenue r USING(month)
), changes AS (
 SELECT *,lag(net_revenue) OVER(ORDER BY month) AS prior_revenue FROM combined
) SELECT *,gross_sales/nullif(orders,0) AS aov,
 (net_revenue-prior_revenue)/nullif(prior_revenue,0) AS revenue_mom FROM changes ORDER BY month;

-- Identity: gross revenue = orders * AOV. Change decomposition (prior AOV then interaction).
WITH monthly AS (
 SELECT *,lag(orders) OVER(ORDER BY month) po,lag(aov) OVER(ORDER BY month) pa
 FROM retailpulse.monthly_sales
) SELECT month,(orders-po)*pa AS order_effect,
 po*(aov-pa) AS aov_effect,(orders-po)*(aov-pa) AS interaction_effect FROM monthly;

-- Repeat customers among known purchasers, not among anonymous invoices.
WITH customer_orders AS (
 SELECT customer_id,count(DISTINCT invoice) n FROM retailpulse.fct_transactions
 WHERE customer_id IS NOT NULL AND is_sale GROUP BY customer_id
) SELECT count(*) customers,count(*) FILTER(WHERE n>1) repeat_customers,
 count(*) FILTER(WHERE n>1)::numeric/nullif(count(*),0) repeat_share FROM customer_orders;

SELECT customer_id,spend,
 sum(spend) OVER(ORDER BY spend DESC,customer_id)/nullif(sum(spend) OVER(),0) cumulative_revenue_share
FROM retailpulse.dim_customers ORDER BY spend DESC;

-- Reconcile gross minus return credits = net. Returns need not match an original sale in the window.
SELECT sum(line_revenue) FILTER(WHERE is_sale) AS gross_sales,
 -sum(line_revenue) FILTER(WHERE is_return) AS return_credit_value,
 sum(line_revenue) AS net_revenue FROM retailpulse.fct_transactions;
