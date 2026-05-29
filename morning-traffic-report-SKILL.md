This is an automated run of a scheduled task. The user is not present to answer questions. For implementation details, execute autonomously without asking clarifying questions — make reasonable choices and note them in your output. "write" actions (e.g. MCP tools that send, post, create, update, or delete), only take them if the task file asks for that specific action. When in doubt, producing a report of what you found is the correct output.

Generate the daily Fidget Newton morning business report. It has four sections: traffic, sales by channel, top products, and store conversion funnel.

---

## Step 1 — Fetch the GA4 cache from GitHub

```
Fetch this URL via web_fetch:
https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME/main/ga4_cache.json
```

Parse the JSON response:
- `yesterday`     — list of dicts: sessionSource, sessionMedium, sessions, activeUsers, conversions, purchaseRevenue, ecommercePurchases
- `prior_7_days`  — same shape; sessions/revenue = 7-day totals (divide by 7 for daily avg)
- `landing_pages` — list of dicts: landingPage, sessions, conversions, purchaseRevenue
- `report_date`   — YYYY-MM-DD — use this as SINCE/UNTIL for Shopify yesterday queries
- `fetched_at`    — ISO timestamp UTC

**Staleness check:** if `fetched_at` is more than 26 hours old, open the report with:
"⚠️ Cache is stale (fetched [TIME]). The GitHub Actions workflow may have failed — check the Actions tab in the repo."

If the fetch fails entirely, open the report with:
"⚠️ Could not fetch GA4 cache from GitHub. Check that the repo is public (or that the URL is correct) and that the Actions workflow has run at least once."

Compute the 7-day prior date range: `prior_start` = report_date minus 8 days, `prior_end` = report_date minus 2 days (i.e. the 7 days before yesterday).

---

## Step 2 — Pull Shopify data

Use the Shopify run-analytics-query tool for these four queries. Substitute `report_date` as the SINCE/UNTIL date for yesterday queries, and `prior_start`/`prior_end` for the 7-day queries.

**Channel — yesterday:**
`FROM sales SHOW orders, gross_sales, net_sales GROUP BY sales_channel SINCE [report_date] UNTIL [report_date]`

**Channel — prior 7 days:**
`FROM sales SHOW orders, gross_sales, net_sales GROUP BY sales_channel SINCE [prior_start] UNTIL [prior_end]`

Drop "Draft Orders" from the channel table — those are unpaid internal records, never real revenue.

**Top products — yesterday:**
`FROM sales SHOW orders, gross_sales GROUP BY product_title ORDER BY gross_sales DESC LIMIT 6 SINCE [report_date] UNTIL [report_date]`

**Store funnel — yesterday:**
`FROM sessions SHOW sessions, sessions_with_cart_additions, sessions_that_reached_checkout, sessions_that_completed_checkout, conversion_rate SINCE [report_date] UNTIL [report_date]`

---

## Step 3 — Compute GA4 traffic table

- `yesterday` sessions: use directly
- `prior_7_days` sessions: divide by 7 for daily avg
- Compute % change: (yesterday - avg) / avg × 100; show as +X% ▲ or -X% ▼; show NEW if no prior avg
- Conv rate: yesterday conversions / yesterday sessions
- Revenue: use `purchaseRevenue` from each cache row directly, formatted as $X. Show — if zero or missing. GA4 undercounts vs Shopify due to ad blockers and tracking gaps. For the gap check, compare GA4 total revenue only against Shopify's Online Store + Shop channel revenue (exclude TikTok and Etsy — those channels never touch the storefront so they will never appear in GA4). If that gap exceeds 15%, note it inline after the traffic table.
- If `ecommercePurchases` differs from `conversions` for any source by more than 1, note it — it means non-purchase conversion events are inflating the Conv column.
- Drop noise rows (admin.shopify.com, (data not available), out.reddit.com) unless they show a significant move
- After the traffic table, if `landing_pages` cache is present, add a compact **Top Landing Pages** row showing the top 5 pages by sessions (page path, sessions, revenue). Highlight if /products/special-orders appears — it's a Special Orders product page that goes through normal checkout.

---

## Report format

---
**Fidget Newton — [DATE]**

**Traffic** *(GA4)*

| Source / Medium | Sessions | vs avg | Conv | Conv rate | Revenue |
|---|---|---|---|---|---|
| direct / none | 49 | +28% ▲ | 3 | 6.1% | $223 |
| google / organic | 26 | +38% ▲ | 2 | 7.7% | $94 |
| ig / social | 8 | +107% ▲ | 1 | 12.5% | — |
| youtube.com / referral | 8 | +75% ▲ | 0 | 0% | — |
| **Total** | **113** | **+42% ▲** | **7** | **6.2%** | **$317** |

Revenue is GA4-reported (purchaseRevenue per source). Total may be lower than Online Store revenue due to ad blockers / tracking gaps — note if gap vs Online Store + Shop exceeds 15%. TikTok and Etsy are excluded from this comparison (they never appear in GA4).

**Sales by Channel** *(Shopify)*

| Channel | Orders | Avg | Revenue | Avg revenue |
|---|---|---|---|---|
| Online Store | 5 | 3.3 | $300 | $205 |
| TikTok Shop | 1 | 2.7 | $17 | $152 |
| Etsy | 0 | 0.3 | $0 | $11 |
| **Total** | **6** | **6.4** | **$317** | **$375** |

**Top Products** *(yesterday)*

| Product | Orders | Revenue |
|---|---|---|
| Fidget Macarons | 4 | $223 |
| Blood Core Macarons | 1 | $55 |

**Store Funnel** *(Shopify, yesterday)*

| Stage | Count | Rate |
|---|---|---|
| Sessions | 122 | — |
| Added to cart | 9 | 7.4% |
| Reached checkout | 8 | 6.6% |
| Completed checkout | 5 | 4.1% |

**Headline:** [One sentence on the most notable thing — revenue, a channel spike, a funnel drop, a new traffic source.]

**Watch:** [One or two things worth paying attention to — channel imbalances, zero-purchase traffic spikes, TikTok vs Online Store divergence, GMC paid traffic appearing, etc.]
---

Keep commentary to 2–3 sentences max. No filler.

## On failure

If the GA4 cache fetch fails, note it at the top and continue with the Shopify sections.

If a Shopify query fails, note it inline and continue with the remaining sections.
