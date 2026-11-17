-- Sales playbook queries: territory view and account features.
-- :cutoff is the snapshot date. Only orders on or before it are used, so a
-- back-test never sees the future.

-- P1: Territory scorecard
WITH o AS (SELECT * FROM orders WHERE order_date <= :cutoff),
acct AS (
    SELECT c.region, c.customer_id, MAX(o.order_date) AS last_order
    FROM customers c JOIN o USING (customer_id) GROUP BY c.customer_id
),
lines AS (
    SELECT c.region, o.*, (r.order_id IS NOT NULL) AS returned
    FROM o JOIN customers c USING (customer_id) LEFT JOIN returns r USING (order_id)
)
SELECT l.region AS territory,
       (SELECT COUNT(*) FROM acct a WHERE a.region = l.region) AS accounts,
       (SELECT COUNT(*) FROM acct a WHERE a.region = l.region
          AND julianday(:cutoff) - julianday(a.last_order) <= 180) AS active_accounts_180d,
       ROUND(SUM(l.sales), 0) AS revenue,
       ROUND(100.0 * SUM(l.profit) / SUM(l.sales), 1) AS margin_pct,
       ROUND(SUM(l.sales) / COUNT(DISTINCT l.order_id), 0) AS avg_order_value,
       ROUND(100.0 * SUM(CASE WHEN l.discount > 0.2 THEN 1 ELSE 0 END) / COUNT(*), 1) AS heavy_discount_lines_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN l.returned THEN l.order_id END) / COUNT(DISTINCT l.order_id), 1) AS return_pct,
       ROUND(SUM(CASE WHEN l.order_date > date(:cutoff, '-365 days') THEN l.sales ELSE 0 END), 0) AS revenue_last_12m,
       ROUND(SUM(CASE WHEN l.order_date >  date(:cutoff, '-730 days')
                       AND l.order_date <= date(:cutoff, '-365 days') THEN l.sales ELSE 0 END), 0) AS revenue_prior_12m
FROM lines l
GROUP BY l.region
ORDER BY revenue DESC;

-- P2: State whitespace (accounts that are under-penetrated against their territory)
WITH o AS (SELECT * FROM orders WHERE order_date <= :cutoff),
st AS (
    SELECT c.region, c.state, COUNT(DISTINCT c.customer_id) AS accounts,
           SUM(o.sales) AS revenue, SUM(o.sales) / COUNT(DISTINCT c.customer_id) AS revenue_per_account
    FROM customers c JOIN o USING (customer_id) GROUP BY c.state
),
reg AS (SELECT region, SUM(revenue) / SUM(accounts) AS region_rev_per_account FROM st GROUP BY region)
SELECT st.region AS territory, st.state, st.accounts, ROUND(st.revenue, 0) AS revenue,
       ROUND(st.revenue_per_account, 0) AS revenue_per_account,
       ROUND(reg.region_rev_per_account, 0) AS territory_rev_per_account,
       ROUND(100.0 * st.revenue_per_account / reg.region_rev_per_account, 0) AS index_vs_territory
FROM st JOIN reg USING (region)
WHERE st.accounts >= 5
ORDER BY index_vs_territory ASC;

-- P3: Account features for qualification (recency, frequency, monetary, quintiles)
WITH o AS (SELECT * FROM orders WHERE order_date <= :cutoff),
base AS (
    SELECT c.customer_id, c.customer_name, c.segment, c.state, c.region AS territory,
           CAST(julianday(:cutoff) - julianday(MAX(o.order_date)) AS INTEGER) AS recency_days,
           COUNT(DISTINCT CASE WHEN o.order_date > date(:cutoff, '-730 days') THEN o.order_id END) AS orders_24m,
           ROUND(SUM(CASE WHEN o.order_date > date(:cutoff, '-730 days') THEN o.sales ELSE 0 END), 2) AS sales_24m,
           ROUND(SUM(o.sales), 2) AS lifetime_sales,
           ROUND(100.0 * SUM(o.profit) / SUM(o.sales), 1) AS lifetime_margin_pct
    FROM customers c JOIN o USING (customer_id)
    GROUP BY c.customer_id
)
SELECT *,
       NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
       NTILE(5) OVER (ORDER BY orders_24m, recency_days DESC) AS f_score,
       NTILE(5) OVER (ORDER BY sales_24m) AS m_score
FROM base;
