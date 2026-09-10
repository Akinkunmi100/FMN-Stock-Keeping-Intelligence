# Signal — Supply Chain Control Room & Replenishment Intelligence

**Signal** is an enterprise-grade operational supply chain intelligence and replenishment triage platform. Built for the Supply Chain and Operations leadership teams at **Flour Mills of Nigeria (FMN)**, it monitors SKU inventories across categories, models stochastic lead-time demand, computes exact purchase order deadlines, provides actionable overstock playbooks, and dispatches proactive notifications before stockouts disrupt manufacturing.

---

## 1. Modular Architecture & Humanized Code Layout

The codebase has been refactored into a clean, modular structure. Each file includes docstrings, typed function signatures, and explanatory section headers:

```
FMN Internship Project/
├── app.py                              # Slim entry point wiring UI views together
├── config.py                           # Central business constants, thresholds, z-scores, & colors
├── monitor.py                          # Autonomous scheduled alert runner (CLI, email, webhooks)
├── Dockerfile                          # Production container configuration
├── requirements.txt                    # Project dependencies (Streamlit, Pandas, NumPy, Groq, Plotly)
├── README.md                           # Comprehensive documentation & deployment guide
├── project1_supply_chain_demand.csv    # 180-day transactional dataset (5,040 rows)
├── test_app_verification.py           # Core pipeline & backward-compatibility test suite
├── test_enhanced_features.py           # Verification for timing, overstock, Plotly charts, & alerts
│
├── core/                               # Core mathematical & analytical engines
│   ├── __init__.py
│   ├── data_pipeline.py                # CSV ingestion, deduplication, bounded interpolation, & ABC Pareto
│   ├── demand_model.py                 # Censored-demand correction, blended velocity, & DOW seasonality
│   ├── inventory_engine.py             # Stochastic safety stock, ROP, ROQ, order timing, & overstock
│   ├── backtest.py                     # 3,900+ checkpoint rolling-origin walk-forward validation
│   └── alerts.py                       # Automated email digest and Slack/Teams/Generic webhooks
│
├── ai/                                 # AI intelligence & natural language engine
│   ├── __init__.py
│   ├── llm_client.py                   # Free-tier Groq client (Llama-3.3-70B) & offline fallback
│   └── grounding.py                    # Anti-hallucination validation, evidence builder, & chat router
│
└── ui/                                 # Visual components & presentation layer
    ├── __init__.py
    ├── styles.py                       # Central CSS design system, typography, & color tokens
    ├── charts.py                       # Reusable interactive Plotly charts (donut, pareto, lines, gauge)
    ├── hero.py                         # Executive hero banner & top KPI cards
    ├── attention_queue.py              # Filterable triage table, timing deadlines, & CSV export
    ├── sku_detail.py                   # Deep-dive analytics, interactive simulator, & AI diagnosis
    ├── backtest_view.py                # Empirical validation heatmap & operational trade-off analysis
    └── chat_view.py                    # Multi-turn conversational Q&A interface
```

---

## 2. Free AI Model for Operational Summaries

* **Provider**: **Groq Cloud** using open-weights `llama-3.3-70b-versatile`.
* **100% Free**: Groq provides free API access with **no credit card required** (1,000 requests/day allowance).
* **Obtaining a Free API Key**:
  1. Visit [console.groq.com](https://console.groq.com)
  2. Sign in with GitHub or Google
  3. Create an API key in 30 seconds
* **Zero-Dependency Local Fallback**: If no `GROQ_API_KEY` is configured or the system is offline, Signal automatically uses an evidence-grounded deterministic engine. The platform is **100% functional without an API key**.

---

## 3. Interactive Plotly Charts for Stakeholder Insights

Signal replaces static tables with 7 interactive **Plotly visualizations** (supporting hover tooltips, zoom, pan, and cross-filtering):

| Visualization | Location | Strategic Purpose |
|---|---|---|
| **Portfolio Risk Donut** | Attention Queue | Executive status breakdown (Critical, High, Medium, Low) |
| **ABC Pareto Volume Bar** | Attention Queue | Daily volume contribution across ABC tiers |
| **Stockout Countdown Bar** | Attention Queue | Visual countdown of on-hand days vs. supplier lead time |
| **Stock Trajectory Line** | SKU Detail | 6-month historical stock vs. Reorder Point & Safety Stock lines |
| **Demand & Receipts Area/Bar**| SKU Detail | Daily sales outflow vs. incoming delivery spikes |
| **Speedometer Risk Gauge** | SKU Detail | 0–100 composite risk score with intuitive color zones |
| **Backtest Confusion Heatmap**| Validation Tab | True Positives, False Alarms, and Missed Crises matrix |

---

## 4. Standardized Color-Coded Indicators

Signal employs an unambiguous color language across cards, badges, charts, and table rows:

| Indicator / Status | Hex Code | Visual Marker | Operational Definition |
|---|---|---|---|
| **Critical** | `#E74C3C` | 🔴 Vibrant Red | Risk $\ge 75$, stock below supplier lead-time coverage |
| **High** | `#E67E22` | 🟠 Warm Amber | Risk $50–74$, stock approaching reorder point |
| **Medium** | `#F1C40F` | 🟡 Caution Yellow | Risk $30–49$, within standard monitoring buffer |
| **Low / On Track** | `#27AE60` | 🟢 Forest Green | Risk $< 30$, healthy stock posture |
| **Overstock Risk** | `#2980B9` | 🔵 Steel Blue | Coverage exceeds limit ($> 28$d), surplus working capital |
| **Class A Badge** | `#1E8449` | 🏷️ Emerald Pill | Top 70% volume drivers (98% service level, $z=2.05$) |
| **Class B Badge** | `#D4AC0D` | 🏷️ Amber Pill | Next 20% volume drivers (95% service level, $z=1.65$) |
| **Class C Badge** | `#7F8C8D` | 🏷️ Slate Pill | Tail 10% volume drivers (90% service level, $z=1.28$) |

---

## 5. Replenishment Order Timing & Exact Deadlines

> *"When it is ordered soon, does it give a time or timeframe to order?"*

**Yes.** Signal computes exact calendar dates and remaining countdown windows for every SKU:

### Mathematical Formulation
1. **Projected Stockout Date**:
   $$\text{Days to Stockout} = \left\lfloor \frac{\text{Current Closing Stock}}{\text{Daily Demand Velocity}} \right\rfloor$$
   $$\text{Stockout Date} = \text{Current Date} + \text{Days to Stockout}$$
2. **Order-By Replenishment Deadline**:
   $$\text{Order-By Date} = \text{Stockout Date} - \text{Supplier Lead Time (Days)}$$
3. **Urgency Classification**:
   - 🔴 **OVERDUE**: $\text{Order-By Date} < \text{Current Date}$ (Order should have already been placed)
   - 🚨 **ORDER TODAY**: $\text{Order-By Date} == \text{Current Date}$
   - 🟠 **ORDER IN 1–3D**: $\text{Order-By Date}$ is within 1 to 3 days
   - 🟡 **ORDER IN 4–7D**: $\text{Order-By Date}$ is within 4 to 7 days
   - 🟢 **BUFFER HEALTHY**: Safe buffer exists beyond 7 days

These dates are displayed on the Attention Queue table, the SKU deep-dive panel, the CSV export file, and automated email alerts.

---

## 6. Overstock Analytics & 5-Point Operational Action Playbook

> *"Recommended action for overstocked needs review and what the metrics are for it."*

When inventory exceeds policy thresholds ($>28$ days of supply for established SKUs, $>21$ days for new launches with stock $>1.5\times\text{ROP}$), Signal computes:

### Overstock Metrics
* **Excess Inventory Units**: $\text{Current Stock} - \text{Target Order-Up-To Level } (S)$
* **Days Over Maximum Target**: $\text{Days of Coverage} - \text{Coverage Limit}$
* **Working Capital Impact**: Quantifies surplus inventory tying up liquidity.

### 5-Point Action Playbook (Displayed in the UI)
1. **Freeze Scheduled POs**: Freeze subsequent purchase orders until stock depletes to target level.
2. **Inter-Warehouse Balancing**: Reallocate surplus units to regional satellite depots experiencing low coverage.
3. **Commercial Acceleration**: Coordinate with commercial and sales teams for targeted volume bundling or promotions.
4. **Structural Demand Audit**: Review sales patterns to verify if recent demand reflects permanent decline.
5. **Perishable Shelf-Life Review**: Verify batch manufacturing dates to guard against product expiration and inventory write-downs.

---

## 7. Autonomous Monitoring & Notification Engine (`monitor.py`)

> *"No one is going to sit under the app to monitor the SKUs."*

Signal includes a standalone CLI monitoring script (`monitor.py`) designed to be scheduled via **Windows Task Scheduler** or **cron**:

```powershell
# Run simulated dry-run (logs results to console without sending network packets)
python monitor.py --dry-run

# Dispatch email digest to procurement distribution list
python monitor.py --email

# Post alert cards to Slack or Microsoft Teams channels
python monitor.py --slack
python monitor.py --teams

# Dispatch across all configured channels
python monitor.py --all
```

### Scheduling via Windows Task Scheduler
```powershell
schtasks /create /tn "SignalDailyInventoryAlert" /tr "python c:\Users\msi\Downloads\FMN Internship Project\monitor.py --all" /sc daily /st 07:00
```

---

## 8. Sharing & Deploying the Application

> *"The app needs to be shared with people. How will that be done?"*

### Option 1: Streamlit Community Cloud (Free, 1-Click)
1. Push this repository to GitHub.
2. Visit [share.streamlit.io](https://share.streamlit.io) and link your GitHub account.
3. Select this repository and click **Deploy**.
4. Streamlit generates a public, shareable URL (e.g. `https://fmn-signal.streamlit.app`).
5. In App Settings $\rightarrow$ Secrets, add:
   ```toml
   GROQ_API_KEY = "your-free-groq-key"
   ```

### Option 2: Render.com (Free Tier)
1. Create a free Web Service on [Render.com](https://render.com) pointing to the GitHub repo.
2. Set Build Command: `pip install -r requirements.txt`
3. Set Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

### Option 3: Docker Container (Internal Enterprise Server)
```powershell
docker build -t fmn-signal-control-room .
docker run -p 8501:8501 fmn-signal-control-room
```

---

## 9. Critical Unaddressed Prediction Drivers (ERP Integration Roadmap)

> *"Which are very significant that would drive the prediction of warning but are not currently addressed?"*

The current dataset captures historical sales, shipments, closing stock, categories, and lead times. To achieve near-zero false alarms, 7 external enterprise signals should be integrated into ERP pipelines:

1. **Open Purchase Orders (POs) & In-Transit Inventory**:
   * *Gap*: The model currently cannot distinguish between an unaddressed stockout risk and one where a massive supplier shipment is already at the warehouse gate.
   * *Fix*: Ingest confirmed open PO lines and expected delivery dates from SAP/Oracle.
2. **Commercial & Promotional Calendar**:
   * *Gap*: Trade discounts or marketing promotions cause sudden 30–150% demand spikes that historical sales cannot predict.
   * *Fix*: Ingest planned promotional event tables with expected lift factors.
3. **Supplier Reliability & OTIF Scores (On-Time In-Full)**:
   * *Gap*: Suppliers frequently deliver late or short. Using a single static lead time underestimates risk for poor vendors.
   * *Fix*: Compute vendor OTIF scores and apply supplier risk multipliers.
4. **Weather, Holidays & Religious Festivities**:
   * *Gap*: Ramadan, Christmas, and rainy seasons create seasonal demand shifts in FMCG food categories.
   * *Fix*: Add cyclical calendar and holiday demand features.
5. **Cross-SKU Cannibalization & Substitution**:
   * *Gap*: When a 500g package stocks out, consumers switch to a 1kg package. The model evaluates each SKU in isolation.
   * *Fix*: Multi-item substitution matrices.
6. **Supplier Minimum Order Quantities (MOQ)**:
   * *Gap*: The mathematical ROQ may recommend 340 units, but the supplier only ships in full pallet batches of 1,000 units.
   * *Fix*: Round ROQ up to the nearest vendor MOQ constraint.
7. **Perishable Shelf Life & Expiration Dates**:
   * *Gap*: Excess flour or perishable goods face spoilage. Overstock risk is far more severe for items nearing expiry.
   * *Fix*: Track batch-level shelf-life dates in WMS.

---

## 10. Local Setup & Verification

### Running the Application
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch Streamlit dashboard
streamlit run app.py
```

### Running the Automated Test Suites
```powershell
# Core pipeline, Pareto, backtest, and backward compatibility
python test_app_verification.py

# Enhanced features: Order timing, overstock diagnostics, Plotly charts, and alerts
python test_enhanced_features.py

# Autonomous alert dispatcher simulation
python monitor.py --dry-run
```
