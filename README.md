# Signal — Supply Chain Early-Warning Tool

**Signal** flags which SKUs need procurement attention before a stockout or overstock situation actually hits — built for the Supply Chain team at Flour Mills of Nigeria (FMN) to open themselves, with no ML background required.

---

## 1. Problem Understanding

The Supply Chain team currently reacts to stockouts and overstock situations *after* the delay or wasted capital has already happened, because nothing surfaces the risk in advance. This tool ingests daily demand, receipts, stock, category, and lead-time data for 28 SKUs (25 established, 3 newly launched) and answers three questions an operator actually needs, every day, without doing the math themselves:

1. **Which SKUs need attention right now, and how urgently?**
2. **Why** — in plain language, grounded in that SKU's real numbers, not a generic template?
3. **What exactly should I do, and by when?**

**What "flagged" means in this system**: a SKU is flagged into one of four action buckets — `Order soon` (active stockout risk, an order is due now or overdue), `Plan replenishment` (stockout risk building but still outside the immediate window), `Overstock risk` (excess capital tied up beyond a coverage-days threshold), or `Monitor closely` (a demand-acceleration signal with no stock trigger yet). A SKU with none of these active triggers is `On track`. Every bucket assignment traces back to an explicit, readable boolean condition in the scoring engine (`core/inventory_engine.py`) — never a black-box threshold a user has to trust blindly.

---

## 2. Approach

### 2.1 Data preparation

The raw CSV has real-world mess, and each piece is handled with an explicit, stated rule (full detail and rationale: [docs/DECISIONS.md](docs/DECISIONS.md)):

| Issue | Rule |
|---|---|
| Missing `units_sold` (90 rows) | Bounded linear interpolation for gaps ≤2 consecutive days; longer gaps left excluded, never guessed at. |
| Missing `closing_stock` (45 rows) | Forward-filled from the last known on-hand count within that SKU's series — a missing reading isn't a reset to zero. |
| Inconsistent category casing (`Snacks` / `SNACKS` / ...) | Casefold + whitespace-collapse; verified to cleanly resolve the raw CSV's 10 variants into 5 categories. |
| Lead-time outliers | Values outside `[1, 60]` days are distrusted and replaced with the SKU's own median (falling back to the dataset-wide median). |

An earlier version of this pipeline had a real bug here: deduplicating `(sku_id, date)` pairs aggregated `units_sold` with a plain `sum()`, and pandas' `sum()` returns `0.0` (not `NaN`) for an all-missing group — silently turning every genuinely-missing sales day into a verified zero-sales day *before* the interpolation logic above ever ran. Fixed by aggregating with `sum(min_count=1)`, which preserves the gap. `test_app_verification.py` asserts this doesn't regress.

### 2.2 Model & validation

This is a **hybrid reorder-point / stochastic safety-stock system**, not a trained forecasting model — deliberately, because ~6 months of history per established SKU is enough to estimate a stable velocity and variance, but not enough to responsibly train and validate a per-SKU ML model, and the 3 new SKUs (~2 weeks of history) would have essentially nothing to train on anyway.

- **Daily demand velocity**: 60% full-history median + 40% EWMA, blending robustness against one-off spikes with responsiveness to a real shift.
- **Seasonality**: day-of-week multipliers applied across the forward lead-time window (not just a flat daily rate).
- **Safety stock**: `SS = z_eff × √(L·σ_D² + D²·σ_L²)` — combines *both* demand variance and lead-time variance, not demand alone, with the service-level z-score (2.05 / 1.65 / 1.28) tiered by ABC class so Class A (top 70% of volume) gets a 98% cycle service level.
- **Validated with a rolling-origin walk-forward backtest** (`core/backtest.py`), not a random train/test split — at each historical date *t*, demand/volatility statistics are computed strictly from data available at *t-1*, which matters because daily readings within a SKU are autocorrelated and a random split would leak future information into the "test" set and inflate the reported metric.

**Current backtest results** (3,926 checkpoints, run against the fixed pipeline):

| Metric | Value | What it means operationally |
|---|---|---|
| Recall | 73.8% | ~3 in 4 real stockouts are caught with advance warning |
| Precision | 18.3% | ~4 in 5 alerts turn out not to become an actual stockout |
| F1 | 29.3% | |
| Accuracy | 59.6% | Not the metric that matters here — see below |

Precision this low is a **deliberate tradeoff, not an accident**: a missed stockout halts a production line; a false alarm costs an operator a few minutes reviewing a SKU that turns out to be fine, or an order placed a little early. Given that asymmetry, the system is tuned toward recall. Accuracy is reported for completeness but is a misleading headline number here — true negatives (ordinary healthy-stock days) vastly outnumber actual stockouts, so a model that flagged nothing would still score high on accuracy while being useless.

### 2.3 Risk thresholds

- **Stockout trigger**: `stock ≤ reorder_point OR days_coverage ≤ lead_time × (1 + 0.5·CV)` — the lead-time comparison widens for a more volatile SKU, since volatility is exactly what erodes a fixed buffer fastest.
- **Overstock trigger**: `days_coverage ≥ coverage_limit AND stock > 1.5 × reorder_point` (established SKUs: 28-day limit = 2× the longest observed supplier lead time in this dataset, 14 days; new SKUs: 21-day limit, tighter because their demand-velocity estimate rests on far less data).
- Every constant behind these formulas is commented in `config.py` with the reasoning tied to either the observed lead-time range or the demand-volatility distribution in this dataset — not a bare number.

### 2.4 New vs. established SKUs

The established approach fails outright on ~2 weeks of data: a per-SKU standard deviation from 12-14 observations is dominated by whichever one unusual day happened to fall in that window. New SKUs instead **inherit their category's median coefficient of variation** (computed only from established SKUs with ≥56 days of history), get a wider safety-stock floor, and use the tighter 21-day overstock limit. Verified live: SKU-2000/2001/2002 all score through a distinct `launch baseline` method path and correctly flag `Order soon` — genuinely, since all three sit at 0 closing stock in the raw data with no receipts recorded yet.

### 2.5 LLM explanations and Q&A — how they're actually grounded

Every flag explanation and every Q&A answer is a **live call to a Groq-hosted model at runtime** (the specific model is configurable in `config.py` — `GROQ_MODEL`/`DEFAULT_GROQ_MODEL`, with an ordered fallback list tried if the primary is unavailable, and the UI displays whichever model id actually answered rather than assuming one), built from that SKU's real computed numbers (`ai/grounding.py`) — not a template with digits substituted in. Two things make this checkable rather than just asserted:

1. **The prompt is built from retrieved data, not general knowledge.** `answer_agentic_question()` routes a free-text question (SKU-specific, category, Class-A, or general portfolio) through a filter against the scored SKU table *first*, and only the filtered subset is serialized into the LLM prompt.
2. **A live response is checked against its own evidence before the user sees it**, via `validate_grounded_numbers()`: every number the model cites must trace back (within 1%/0.5 units) to a number actually present in the evidence or the system prompt. A response that cites an unverifiable figure is discarded and replaced with a deterministic local explanation, with a warning explaining why. (This check existed in the codebase before this fix but was never wired into the actual call path — dead code satisfying the letter of "we have a check" with none of the substance. It's now called on every explanation and every Q&A route, and three real bugs in the check itself — Unicode dash handling, SKU-ID digit false-positives, and a thousands-separator parsing gap — were found and fixed in the process of actually exercising it against live Groq output.)

Spot-checked (both via direct calls and inside the running Streamlit app): SKU-1010's explanation cites stock 112, coverage 0.6 days, ROQ 1,839, order-by 2026-06-26 — all matching its row exactly. SKU-1009's cites stock 9,874, coverage 29.2 days, excess 1,825 units — all matching. Both were live Groq calls, and the two explanations differ in their actual reasoning (one about an overdue PO, the other about holding off purchases on a demand decline), not just in the substituted digits.

---

## 3. How to Run

### Install

```bash
pip install -r requirements.txt
```

### Set the LLM API key (optional — the app is fully functional without one)

Groq's free tier needs no credit card (1,000 requests/day). Get a key at [console.groq.com](https://console.groq.com), then set it via **any** of:

```bash
# Option A: environment variable
export GROQ_API_KEY="your-key-here"

# Option B: .env file in the project root
echo 'GROQ_API_KEY=your-key-here' > .env

# Option C: .streamlit/secrets.toml
echo 'GROQ_API_KEY = "your-key-here"' > .streamlit/secrets.toml
```

Without a key, explanations and Q&A fall back to a deterministic, evidence-based local engine — clearly labeled as such in the UI, never disguised as a live model response.

### Run locally

```bash
streamlit run app.py
```

### Run the verification suite

```bash
python test_app_verification.py
```

Checks (offline, no API key required): every SKU scores without error, the `units_sold`/`closing_stock` gap rules behave as documented, category normalization collapses correctly, at least one established and one new SKU produce an active flag, the backtest runs end-to-end, and the grounding validator correctly accepts grounded text / rejects a fabricated number.

### Deployed URL

**Not yet deployed to a public URL.** The app runs correctly locally (`streamlit run app.py`) and is deployment-ready — `Dockerfile` is production-configured, `requirements.txt` is pinned, and secrets are read from environment variables / `.streamlit/secrets.toml`, never committed. Deploying requires connecting a hosting platform to this repo's GitHub account (Streamlit Community Cloud or Render — see §6 below for exact steps), which is an account-level action outside what an automated pass over the code can complete. Once deployed, replace this line with the live link.

---

## 4. Limitations & Next Steps

- **No public deployment yet** (see above) — this is the single biggest gap between "runs correctly" and "deliverable" per the brief's own checklist.
- **Precision is genuinely low (18.3%)** — by design, given the stated cost asymmetry, but a plant team acting on every alert will spend real time reviewing SKUs that don't stockout. Worth revisiting with real operator feedback on whether the recall/precision balance is right in practice, not just in theory.
- **Severity-threshold calibration gap**: a SKU that is already overdue with a same-day projected stockout (verified case in this dataset: SKU-1010, 0.6 days coverage, order-by date already passed) still scores ~74/100 and displays as "High," not "Critical" (cutoff is 75). Documented in `config.py` rather than silently adjusted, since changing it reclassifies which SKUs show as Critical throughout the dashboard, CSV export, and alert digest — a modeling decision that deserves sign-off, not a unilateral tweak.
- **No fuzzy-matching for category-name spelling variants** (e.g. `Snack` vs `Snacks`) — the current dataset only has casing/whitespace variants, so there was nothing to validate this against. If a future data refresh introduces real spelling drift, this needs revisiting.
- **New-SKU accuracy is inherently the weakest part of the system** — the category-CV-inheritance fallback is a reasonable engineering compromise, not a substitute for real history. Treat new-SKU flags as directionally useful, not as precise as an established SKU's.
- **Lead-time outlier handling is untested against real bad data** — the `[1,60]`-day sanitization logic works (verified by injecting synthetic bad values), but every lead time in the actual dataset happens to already be valid, so this path has never been exercised in production.
- **Missing external signals**: open purchase orders / in-transit stock, promotional calendar, supplier OTIF reliability, holiday/seasonal demand shifts, cross-SKU substitution, supplier MOQ constraints, and shelf-life/expiry are all real drivers of stockout/overstock risk that this dataset doesn't capture. See §7 below for what each would take to add.

---

## 5. Repository Structure

```
FMN Internship Project/
├── app.py                              # Streamlit entry point wiring UI views together
├── config.py                           # Business constants, thresholds (each with a stated reason), z-scores, colors
├── monitor.py                          # Standalone CLI alert dispatcher (email/Slack/Teams), for scheduling outside the app
├── test_app_verification.py            # Offline verification suite — see §3
├── Dockerfile                          # Production container config
├── requirements.txt                    # Pinned dependencies
├── project1_supply_chain_demand.csv    # Source dataset
├── docs/
│   ├── BUILD_BRIEF.md                  # Original problem brief and design questions
│   └── DECISIONS.md                    # Resolved answers to those questions, with rationale
│
├── core/                                # Data + math, no UI/LLM dependencies
│   ├── data_pipeline.py                # Ingestion, dedup, gap handling, ABC Pareto, seasonality priors
│   ├── demand_model.py                 # Censored-demand correction, blended velocity, trend detection
│   ├── inventory_engine.py             # Safety stock, ROP/ROQ, order timing, overstock diagnostics, risk score
│   ├── backtest.py                     # Rolling-origin walk-forward validation
│   └── alerts.py                       # Email/Slack/Teams digest builders and senders
│
├── ai/                                  # LLM grounding — no Streamlit dependency, independently testable
│   ├── llm_client.py                   # Groq client with multi-source key loading and model fallback
│   └── grounding.py                    # Evidence builder, anti-hallucination check, Q&A router
│
└── ui/                                  # Streamlit components and Plotly charts
    ├── styles.py, charts.py, hero.py, attention_queue.py, sku_detail.py, backtest_view.py, chat_view.py
```

---

## 6. Deploying

Two independent decisions: the app framework (already chosen — Streamlit) and the hosting platform (not yet chosen/executed).

**Option A — Streamlit Community Cloud (free, simplest)**
1. Push this repo to GitHub (already has a remote configured).
2. Visit [share.streamlit.io](https://share.streamlit.io), connect the GitHub account, select this repo, click Deploy.
3. In App Settings → Secrets, add `GROQ_API_KEY = "your-free-groq-key"`.
4. Copy the generated public URL into §3 above.

**Option B — Render.com (free tier)**
1. Create a Web Service pointing at this repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. Set `GROQ_API_KEY` as an environment variable in the Render dashboard.

**Option C — Docker (internal server)**
```bash
docker build -t fmn-signal-control-room .
docker run -p 8501:8501 -e GROQ_API_KEY=your-key fmn-signal-control-room
```

---

## 7. Autonomous Monitoring (`monitor.py`)

No one needs to sit watching the dashboard. `monitor.py` is a standalone CLI script meant to be scheduled (Windows Task Scheduler / cron) to run the same scoring engine headlessly and dispatch a digest:

```bash
python monitor.py --dry-run   # simulate, log only, no network calls
python monitor.py --email     # send the digest via SMTP
python monitor.py --slack     # post to a Slack incoming webhook
python monitor.py --teams     # post to a Microsoft Teams webhook
python monitor.py --all       # dispatch across every configured channel
```

Configure via environment variables: `SMTP_SERVER`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_RECIPIENTS`, `SLACK_WEBHOOK_URL`, `TEAMS_WEBHOOK_URL` (see `config.py`'s `ALERT_CONFIG`). Windows Task Scheduler example:

```powershell
schtasks /create /tn "SignalDailyInventoryAlert" /tr "python C:\path\to\monitor.py --all" /sc daily /st 07:00
```

---

## 8. What's Missing at a Glance vs. One Click Away

- **At a glance** (Attention Queue tab, zero clicks): total flagged vs. portfolio size, critical severity count, Class-A-at-risk count, total reorder units, plus 3 portfolio charts (risk donut, ABC volume bar, stockout countdown).
- **One click away**: per-SKU deep dive (stock trajectory, demand/receipts chart, risk gauge, what-if simulator, live AI explanation, full evidence audit table), free-text Q&A, and the backtest/validation tab.

## 9. External Signals Not Yet Integrated

These would meaningfully improve accuracy but require data this dataset doesn't contain:

1. **Open POs / in-transit inventory** — currently can't distinguish an unaddressed risk from one where a shipment is already en route.
2. **Promotional calendar** — trade promotions cause demand spikes historical sales alone can't predict.
3. **Supplier OTIF reliability** — a single static lead time underestimates risk for a chronically late supplier.
4. **Holiday/seasonal calendar** — Ramadan, Christmas, rainy season shift FMCG demand beyond what day-of-week seasonality captures.
5. **Cross-SKU substitution** — SKUs are scored independently; a stockout on one pack size doesn't currently reallocate demand to another.
6. **Supplier MOQ constraints** — the computed ROQ may not match real order-batch minimums.
7. **Shelf-life/expiry** — overstock risk is understated for perishables nearing expiry.
