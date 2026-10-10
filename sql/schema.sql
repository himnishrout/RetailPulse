CREATE SCHEMA IF NOT EXISTS retailpulse;
CREATE TABLE IF NOT EXISTS retailpulse.stg_transactions (
 invoice text, product_id text, description text, quantity double precision,
 invoice_date timestamp, unit_price double precision, customer_id double precision,
 country text, source_sheet text, source_row bigint
);
CREATE TABLE IF NOT EXISTS retailpulse.dim_customers (
 customer_id bigint PRIMARY KEY, first_purchase timestamp NOT NULL,
 last_purchase timestamp NOT NULL, country text, orders bigint NOT NULL,
 spend numeric(20,2), recency_days bigint, r_score integer, f_score integer,
 m_score integer, segment text, snapshot_date timestamp
);
CREATE TABLE IF NOT EXISTS retailpulse.dim_products (
 product_id text PRIMARY KEY, description text
);
CREATE TABLE IF NOT EXISTS retailpulse.dim_dates (
 date timestamp PRIMARY KEY, year integer, month text
);
CREATE TABLE IF NOT EXISTS retailpulse.fct_transactions (
 line_id bigint PRIMARY KEY, invoice text NOT NULL,
 product_id text NOT NULL REFERENCES retailpulse.dim_products(product_id),
 description text, quantity bigint NOT NULL CHECK(quantity<>0),
 invoice_date timestamp NOT NULL, unit_price numeric(20,6) NOT NULL CHECK(unit_price>0),
 customer_id bigint, country text, source_sheet text, source_row bigint,
 is_sale boolean NOT NULL, is_return boolean NOT NULL,
 is_cancellation_invoice boolean NOT NULL, line_revenue numeric(20,2),
 date timestamp NOT NULL REFERENCES retailpulse.dim_dates(date),
 CHECK(is_sale=(quantity>0)), CHECK(is_return=(quantity<0))
);
-- No customer FK: a known return-only customer need not have a qualifying purchase.
-- dim_customers is the observed purchasing population; unmatched customer IDs remain auditable.
CREATE INDEX IF NOT EXISTS ix_customer_date ON retailpulse.fct_transactions(customer_id,invoice_date);
CREATE INDEX IF NOT EXISTS ix_invoice ON retailpulse.fct_transactions(invoice);
CREATE TABLE IF NOT EXISTS retailpulse.monthly_sales (
 month text PRIMARY KEY, gross_sales numeric(20,2), return_value numeric(20,2),
 net_revenue numeric(20,2), orders bigint, aov double precision,
 net_revenue_mom double precision, partial_month boolean
);
CREATE TABLE IF NOT EXISTS retailpulse.cohort_retention (
 cohort text, month_index integer, cohort_size bigint, active_customers double precision,
 retention double precision, fully_observed boolean, PRIMARY KEY(cohort,month_index)
);
CREATE TABLE IF NOT EXISTS retailpulse.product_performance (
 product_id text PRIMARY KEY REFERENCES retailpulse.dim_products(product_id),
 gross_sales numeric(20,2), return_value numeric(20,2), sale_units bigint,
 return_units bigint, return_value_ratio double precision
);
CREATE TABLE IF NOT EXISTS retailpulse.customer_scores (
 customer_id bigint PRIMARY KEY REFERENCES retailpulse.dim_customers(customer_id),
 recency_days double precision, tenure_days double precision, orders bigint,
 spend double precision, aov double precision, products bigint, orders_30 double precision,
 orders_90 double precision, spend_90 double precision, return_lines double precision,
 snapshot_date timestamp, repeat_probability double precision CHECK(repeat_probability BETWEEN 0 AND 1), model text
);
