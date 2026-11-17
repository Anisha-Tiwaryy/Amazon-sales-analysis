-- Amazon Sales Analysis: the 10 business questions.
-- Each block starts with "-- Q<n>: <title>" so run_analysis.py can run and save it.

-- Q1: Top five customers by total profit
SELECT c.customer_id, c.customer_name, c.segment, c.state,
       ROUND(SUM(o.profit), 2) AS total_profit,
       ROUND(SUM(o.sales), 2)  AS total_sales
FROM orders o JOIN customers c USING (customer_id)
GROUP BY c.customer_id
ORDER BY total_profit DESC
LIMIT 5;

-- Q2: Average quantity ordered per product category
SELECT p.category, ROUND(AVG(o.quantity), 2) AS avg_quantity, COUNT(*) AS order_lines
FROM orders o JOIN products p USING (product_id)
GROUP BY p.category
ORDER BY avg_quantity DESC;

-- Q3: Top five products by total revenue
SELECT p.product_id, p.product_name, p.sub_category,
       ROUND(SUM(o.sales), 2) AS total_revenue, SUM(o.quantity) AS units
FROM orders o JOIN products p USING (product_id)
GROUP BY p.product_id
ORDER BY total_revenue DESC
LIMIT 5;

-- Q4: Five products whose revenue fell the most versus the previous year (2017 vs 2016)
WITH yearly AS (
    SELECT product_id,
           SUM(CASE WHEN strftime('%Y', order_date) = '2016' THEN sales ELSE 0 END) AS rev_2016,
           SUM(CASE WHEN strftime('%Y', order_date) = '2017' THEN sales ELSE 0 END) AS rev_2017
    FROM orders GROUP BY product_id
)
SELECT y.product_id, p.product_name, p.sub_category,
       ROUND(y.rev_2016, 2) AS rev_2016, ROUND(y.rev_2017, 2) AS rev_2017,
       ROUND(y.rev_2017 - y.rev_2016, 2) AS change,
       ROUND(100.0 * (y.rev_2017 - y.rev_2016) / y.rev_2016, 1) AS change_pct
FROM yearly y JOIN products p USING (product_id)
WHERE y.rev_2016 > 0 AND y.rev_2017 < y.rev_2016
ORDER BY change ASC
LIMIT 5;

-- Q5: Most profitable sub-category (all sub-categories ranked)
SELECT p.sub_category, p.category,
       ROUND(SUM(o.profit), 2) AS total_profit,
       ROUND(100.0 * SUM(o.profit) / SUM(o.sales), 1) AS margin_pct
FROM orders o JOIN products p USING (product_id)
GROUP BY p.sub_category
ORDER BY total_profit DESC;

-- Q6: States with the highest order volumes
SELECT c.state, c.region, COUNT(DISTINCT o.order_id) AS orders,
       COUNT(DISTINCT o.customer_id) AS customers, ROUND(SUM(o.sales), 2) AS sales
FROM orders o JOIN customers c USING (customer_id)
GROUP BY c.state
ORDER BY orders DESC
LIMIT 10;

-- Q7: Month with the most orders (all years combined)
SELECT CAST(strftime('%m', order_date) AS INTEGER) AS month,
       COUNT(DISTINCT order_id) AS orders, ROUND(SUM(sales), 2) AS sales
FROM orders
GROUP BY month
ORDER BY orders DESC;

-- Q8: Profit margin per sale (profit / sales), summarised by discount band
WITH lines AS (
    SELECT o.*, 100.0 * o.profit / o.sales AS margin_pct,
           CASE WHEN discount = 0 THEN '0%'
                WHEN discount <= 0.2 THEN '1-20%'
                WHEN discount <= 0.4 THEN '21-40%'
                ELSE '41%+' END AS discount_band
    FROM orders o
)
SELECT discount_band, COUNT(*) AS order_lines,
       ROUND(AVG(margin_pct), 1) AS avg_margin_pct,
       ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS weighted_margin_pct,
       ROUND(100.0 * SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS loss_making_pct
FROM lines
GROUP BY discount_band
ORDER BY discount_band;

-- Q9: Each sub-category's percentage contribution to total sales
SELECT p.sub_category,
       ROUND(SUM(o.sales), 2) AS sales,
       ROUND(100.0 * SUM(o.sales) / (SELECT SUM(sales) FROM orders), 2) AS contribution_pct
FROM orders o JOIN products p USING (product_id)
GROUP BY p.sub_category
ORDER BY contribution_pct DESC;

-- Q10: Top two categories by returned orders, with return percentage
WITH order_cat AS (
    SELECT o.order_id, p.category
    FROM orders o JOIN products p USING (product_id)
    GROUP BY o.order_id, p.category
)
SELECT oc.category,
       COUNT(DISTINCT CASE WHEN r.order_id IS NOT NULL THEN oc.order_id END) AS returned_orders,
       COUNT(DISTINCT oc.order_id) AS orders,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN r.order_id IS NOT NULL THEN oc.order_id END)
             / COUNT(DISTINCT oc.order_id), 2) AS return_pct
FROM order_cat oc LEFT JOIN returns r USING (order_id)
GROUP BY oc.category
ORDER BY returned_orders DESC
LIMIT 2;
