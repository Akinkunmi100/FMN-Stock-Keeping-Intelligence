# Signal: supply chain early-warning tool

Signal is a Streamlit dashboard for reviewing inventory risk across a portfolio of SKUs. It reads the daily demand, receipt, stock, category, and lead-time data in `project1_supply_chain_demand.csv` and turns it into a short, ranked list of products that may need action.

It is designed to support a daily supply-chain review.

## Problem understanding

Even though the team already has daily records, but the records do not answer the operational question quickly enough:

> Which SKUs should someone look at today, what is driving the warning, and how much time is left to respond?

Hence the reason behind this supply chain early-warning signal. The app does the first pass over the data. It shows the attention queue first, then lets a user open a SKU for the numbers behind its status. The LLM assistant can answer questions such as `Why is SKU-1004 flagged?` or `Which SKUs need attention this week?`.

A SKU is flagged when one of these conditions is true:

- **Order soon**: stock is inside the replenishment window and the projected order deadline is immediate or overdue.
- **Plan replenishment**: the SKU is below its reorder point, but its current coverage is still longer than the supplier lead time.
- **Overstock risk**: stock covers more days than the configured target and is materially above the reorder point.
- **Monitor closely**: recent demand is accelerating while coverage is already relatively close to the lead time.
- **On track**: none of the warning conditions is currently true.

The status comes from readable rules in `core/inventory_engine.py`.


## Approach

### Data preparation

The pipeline in `core/data_pipeline.py` prepares the CSV before scoring:

1. Rows with the same `sku_id` and `date` are combined. Sales and receipts are added, while the last closing-stock reading is kept.
2. A missing `units_sold` value is linearly interpolated only when it is part of a bounded gap of two days or fewer. Longer gaps remain missing and are left out of demand statistics.
3. A missing `closing_stock` reading is carried forward from the last known reading for that SKU. The original value is kept in `closing_stock_raw` for auditability.
4. Categories are trimmed, case-folded, and whitespace-normalized. The current dataset has casing/spacing differences but no unresolved spelling conflict.
5. Lead times outside 1-60 days are treated as invalid. The SKU median is used when possible; otherwise the dataset median is used.
6. SKUs are given an ABC class from total unit volume. This is a volume-based priority, not a revenue or production-criticality ranking, because the dataset contains no prices, margins, or production-dependency fields.
7. Portfolio day-of-week multipliers are calculated and used when projecting demand across a supplier lead-time window.

For the supplied file, the pipeline reads 4,551 raw rows, reduces them to 4,536 SKU/date records, finds 90 missing demand values, interpolates 89, and leaves 1 outside the interpolation rule. There are 45 missing closing-stock readings; these are carried forward before scoring.

### Inventory risk model

This is a transparent hybrid of reorder-point logic and stochastic safety stock. 


For each SKU, the scoring engine:

1. Removes demand observations from zero-stock days when at least 14 positive-stock days are available. This reduces the chance of treating an unavailable product as a low-demand product (if the shelf was empty, that's not evidence nobody wanted to buy it).
2. Estimates daily demand as a blend of the full-history median and a recent EWMA (an average that weights the last few days more heavily than older ones): 60% median and 40% EWMA.
3. Projects demand across the lead-time window using day-of-week multipliers, so a SKU that sells more on Wednesdays gets a forecast that reflects that instead of a flat daily average.
4. Calculates safety stock (the buffer held above expected demand) from demand variability, lead-time variability, ABC service-level settings, and a category-level tail-risk adjustment.
5. Calculates `reorder point = projected lead-time demand + safety stock`: the stock level that should trigger a new order.
6. Calculates an order-up-to level and recommended order quantity for SKUs that need replenishment.
7. Calculates `days of coverage = closing stock / estimated daily demand`.
8. Assigns the action bucket, a 0-100 risk score, and a severity level.
9. Writes a one-paragraph, plain-language explanation of what's driving that status (see "Two kinds of explanation" below).

The main triggers are:

- Stockout risk when `stock <= reorder point` or `days of coverage <= lead time * (1 + 0.5 * CV)`. A recent receipt can suppress the warning when it indicates that replenishment is active and stock is above the safety buffer.
- Overstock risk when coverage is at least 28 days for established SKUs (21 days for new SKUs) and stock is more than 1.5 times the reorder point.
- Demand acceleration when the recent lead-time-sized demand window is at least 15% above the preceding comparison window and coverage is within 2.5 lead times.

The risk score is a separate severity signal. It combines coverage depletion, demand acceleration, volatility, and proximity to the reorder point, then applies an ABC multiplier. The bucket remains rule-based so a user can see why an SKU entered the queue.

### Two kinds of explanation

The dashboard uses two different mechanisms to explain a SKU:

1. **"What happened" (always on, no API call).** Every scored SKU gets a one-paragraph diagnosis, the exact numbers that put it in its bucket, written by a plain Python function (`synthesize_what_happened()` in `core/inventory_engine.py`) that fills a template with that SKU's real figures. It's visible immediately in the attention queue and the SKU detail page, costs nothing, and needs no internet connection, and is not AI-generated.


2. **"Operational diagnosis" (on demand, needs Groq).** A longer, more conversational explanation generated at runtime by a live call to a Groq-hosted language model.

### New SKUs

SKUs with fewer than 56 days of history use a launch baseline rather than the established-SKU path. Their own volatility estimate is too uncertain to use on its own, so the model borrows the median coefficient of variation from established SKUs in the same category and applies a wider safety-stock floor.

The three new SKUs in the supplied file have 12 days of history each. They are scored, but the detail view identifies the launch method so their results are not presented with the same confidence as a six-month SKU.

### Validation

The project includes a rolling-origin backtest in `core/backtest.py`. It uses only data available before each historical checkpoint and checks whether a stockout occurred within the SKU's lead-time horizon.

On the current dataset it evaluates 3,926 checkpoints:

| Measure | Result | Meaning |
| --- | ---: | --- |
| Recall | 73.8% | Share of stockout events that received an earlier warning |
| Precision | 18.3% | Share of warnings followed by a stockout in the tested horizon |
| F1 | 29.3% | Combined precision/recall measure |
| False-alarm rate | 42.2% | Share of healthy checkpoints that were still flagged |
| Accuracy | 59.6% | Overall classification accuracy; less useful than recall/precision here |

These figures describe the stockout-warning benchmark in this dataset. They do not validate overstock alerts, the composite score, the Groq explanation.
Precision is low, so this should be treated as a review queue.

### Explanations and Q&A

When `GROQ_API_KEY` is available, the app sends a runtime request to Groq. The model is configured through `GROQ_MODEL`; the current default and fallback list are in `config.py`.

Before making a request, the app retrieves relevant evidence:

- A SKU question retrieves one scored SKU.
- A category question retrieves the SKUs in that category.
- A Class A question retrieves ABC-A SKUs.
- A general portfolio question retrieves the summary and the highest-priority flagged SKUs.

The evidence includes stock, demand estimates, coverage, lead time, reorder point, safety stock, recommended order quantity, order timing, trend, volatility, ABC class, score, severity, and the method used for the SKU. A numeric grounding check rejects a live answer if it cites a number that is not present in the retrieved evidence. The user then sees a local evidence-based explanation instead.

Without a Groq key, the dashboard still works. Explanations and Q&A use the local deterministic fallback and are labelled as local rather than being presented as AI output.

## How to run

### Requirements

- Python 3.11 or newer
- The supplied CSV, unless another file is provided through `SUPPLY_CHAIN_DATA_PATH`
- Internet access and a Groq API key only if live explanations or Q&A are required

### Install and start the app

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

`requirements.txt` uses compatible version ranges. For a production deployment, generate and commit a lock file after choosing the deployment Python version.

### Enable Groq

The app checks, in order:

1. `GROQ_API_KEY` in the environment
2. `GROQ_API_KEY` in `.streamlit/secrets.toml`
3. `GROQ_API_KEY` in a local `.env` file

PowerShell:

```powershell
$env:GROQ_API_KEY = "your-key"
$env:GROQ_MODEL = "openai/gpt-oss-120b"
streamlit run app.py
```

The key files are ignored by Git. Do not commit them.

### Run checks

```bash
python test_app_verification.py
```

The offline verification script checks data preparation, missing-value handling, category normalization, all 28 SKUs, new-SKU scoring, the backtest, and the numeric grounding validator. It does not call Groq.

### Run the monitor

`monitor.py` runs the same scoring pipeline without opening the dashboard:

```bash
python monitor.py --dry-run
```

Email, Slack, and Microsoft Teams delivery are available through environment variables. Sending notifications has not been exercised against live recipient accounts in this repository.

### Use another data file

The default input is the supplied CSV beside `app.py`. To point the app at another file with the same columns:

```powershell
$env:SUPPLY_CHAIN_DATA_PATH = "C:\data\inventory.csv"
streamlit run app.py
```

### Deployment

The application is deployed live on Streamlit Community Cloud:

- **Live Application**: [Signal - Supply Chain Intelligence](https://fmn-stock-keeping-intelligence-wvs2ie3vgyrj8dapy8tcgx.streamlit.app/)

#### Streamlit Community Cloud Setup

1. Push the repository to GitHub.
2. Deploy the app from your repository using `app.py` as the main entry point.
3. Add `GROQ_API_KEY` under the app settings in **Secrets**.

#### Container Deployment (Docker)

```bash
docker build -t signal-supply-chain .
docker run -p 8501:8501 -e GROQ_API_KEY=your-key signal-supply-chain
```

## Limitations and next steps

These are the limitations that matter when interpreting the current results.

1. **The backtest only validates the stockout-warning half of the system.** The 73.8%/18.3% recall/precision numbers above describe one trigger (`Order soon`) against one outcome (did a stockout actually happen). Overstock alerts, the composite risk score, and the written diagnosis have no equivalent empirical check yet: they're built from the same real numbers, but they haven't been scored against historical outcomes the way the stockout trigger has.
2. **There is no cost data in this dataset, so the recall-over-precision tradeoff is a judgment call, not a calculated optimum.** A missed stockout clearly matters more than a false alarm, but by how much is unknown, because the file has no price, margin, or downtime-cost fields. The 15% trend threshold, 21/28-day coverage limits, and score weights in `config.py` are reasoned starting points, not figures fitted to this data, and they should move once real cost numbers exist.
3. **ABC priority is volume only, and volume isn't the same as importance.** A SKU is Class A because it sells a lot of units, not because it's expensive, hard to substitute, or contractually committed to a customer. A low-volume but critical option would currently rank below where the business might actually want it.
4. **The three new SKUs have 12 days of history each: not enough for a SKU-specific forecast.** The model deliberately borrows category-level volatility as a stand-in, which is a reasonable fallback, not a substitute for real history. Treat their flags as directional until more data accumulates.
5. **Supplier-side visibility is incomplete.** The data has daily receipts but no open purchase orders, confirmed inbound quantities, or supplier reliability track record. A shipment that's already en route looks identical to one that was never ordered, and a missing stock count is carried forward from the last known reading with no limit on how stale it can get before someone should double-check it by hand.
6. **Seasonality stops at day-of-week.** There's no adjustment for promotions, holidays, or one-off demand shocks. A marketing push or a Ramadan effect would currently look identical to organic demand growth to this model.

The single highest-value next step: start recording what actually happens after each alert, whether the SKU stocked out, whether an order was placed, what arrived, and whether the warning was useful. That closes the loop this dataset is currently missing, turns the threshold choices in point 2 from reasoned guesses into evidence, and is the only way to know whether flagging fewer, more-precise alerts would actually save more than it costs.

## Repository map

```text
app.py                         Streamlit entry point
config.py                      Paths, model settings, thresholds, colours, alert settings
core/data_pipeline.py          Cleaning, deduplication, gap handling, ABC and seasonality
core/demand_model.py           Demand velocity, censoring correction, trend and volatility
core/inventory_engine.py       Safety stock, reorder points, timing, buckets and scores
core/backtest.py               Rolling-origin stockout-warning benchmark
core/alerts.py                 Alert digest and optional notification delivery
ai/llm_client.py               Groq client, model fallback, and key loading
ai/grounding.py                Evidence construction, Q&A routing and numeric validation
ui/                            Streamlit views and charts
monitor.py                     Command-line monitoring entry point
test_app_verification.py       Offline verification script
docs/DECISIONS.md              Design decisions and rationale
```
