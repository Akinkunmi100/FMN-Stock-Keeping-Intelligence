# Supply Chain Early-Warning Tool — Build Brief

You are a supply chain data analyst and builder creating a diagnostic tool for your team — one they can open themselves to see which SKUs need action before problems hit production.

## The Core Problem

The Supply Chain team reacts instead of acting. They discover stockouts and overstock situations after delays or wasted capital have already happened. You're building their early-warning system: something that flags which SKUs need attention *now*, explains *why* in plain language grounded in real numbers, and gives enough lead time to act.

## What You're Building

A tool that:
- Ingests daily demand, stock, receipts, category, and lead time data from `project1_supply_chain_demand.csv`
- Automatically identifies which SKUs are at risk (running low, overstocked, or heading for trouble)
- Surfaces each risk with a plain-language explanation an analyst would actually trust
- Runs as an interactive web app (Streamlit or Gradio) a business user can operate without help
- Is deployed to a public URL
- Includes a free-text question box — "why is SKU-1004 flagged?", "which SKUs need attention this week?" — answered from the underlying data, not canned text

## The Data

`project1_supply_chain_demand.csv` contains daily units sold, units received, closing stock, category, and lead time for 25 established SKUs (~6 months of history) and 3 newly launched SKUs (~2 weeks of history). Expect real-world mess: missing values in `units_sold`, inconsistent category casing, and — for the new SKUs — not enough history to compute the same statistics you'd use for the established ones. Don't assume these away; how you handle them is part of what's being evaluated.

## Your Approach

There's no prescribed model, method, or build order here. Reason from how the data actually behaves and defend every choice against it. Before you work through the questions below, decide for yourself what's the smallest piece you can build and validate first — does the flagging logic hold up on its own, can the LLM produce a genuinely grounded explanation — before you invest in the full app around it. Let that judgment carry through everything that follows; you don't need to write it up separately, but it should be visible in the choices you make.

## Design Questions to Work Through

**Data Preparation**
- Which gaps in `units_sold` should be imputed, and which rows should simply be excluded? What's your rule, and why?
- How will you normalize category casing, and what do you do if two "same" categories still don't fully agree once normalized?
- What in the lead-time column would make you distrust a value, and what do you do when you find one?

**Model Selection & Validation**
- What approach identifies risk here — reorder points, safety stock, days-of-inventory, forecasting, anomaly detection, or a hybrid? Why does it fit this business problem, given only ~6 months for established SKUs and ~2 weeks for new ones?
- What's your evaluation metric, and how do you validate it without enough new-SKU history to hold out a real test set?

**Risk Thresholds & Formulas**
- Define the exact calculation that triggers each flag type (stockout risk, overstock risk, and anything else you identify). State the threshold and the formula, and explain how lead time shapes it.
- Why that threshold and not a stricter or looser one — what's the cost of a false alarm vs. a missed flag here?

**New vs. Established SKUs**
- Where does your established-SKU approach simply fail on 2 weeks of data?
- What fallback do you use for new SKUs, and how do you set a meaningful threshold without 6 months of reference data to lean on?

**Risk Classification**
- Translate flags into plain-language action buckets (e.g., "Order Soon," "Overstock Risk," "Monitor Closely"). What decides which bucket a SKU lands in, and how do you keep that logic transparent enough that your team trusts it without asking you?

**Grounding the LLM, Not Just Prompting It**
- Every flag explanation must come from an LLM call at runtime, grounded in that SKU's actual numbers — not a template with variables swapped in.
- What exact figures (demand trend, stock level, lead time, days of coverage, whatever else you compute) get passed into the prompt, and how do you structure them so the explanation can't drift from what's true?
- How do you know the LLM isn't hallucinating a number or a reason that isn't actually in the data you gave it? What check, if any, catches that before the user sees it?
- The question box works the same way: retrieve the relevant SKU data first, then pass it plus the user's question to the LLM. What does retrieval actually look like for "which SKUs need attention this week?" — how do you decide what's relevant and hand it over?

**Tool Structure**
- What does a user see in the first five seconds of opening the tool, and what do they click to go deeper?
- What's the difference between what belongs at a glance and what belongs one click away?

## Deliverables

1. **Working application** — deployed and functional, not just runnable locally.
2. **Code repository** — clean enough that another engineer could pick it up without asking you anything. Structure it however fits your design; don't force a layout that doesn't match what you built.
3. **README.md** covering:
   - **Problem Understanding** — the problem restated in your own words, and what "flagged" means in your system
   - **Approach** — what you built, the model/method you chose and why, what you validated first and why, your evaluation metric and results, and how the LLM explanations and Q&A are grounded
   - **How to Run** — setup steps, dependencies, exact commands (e.g. `pip install -r requirements.txt`, setting the LLM API key, the run command), and the deployed link
   - **Limitations & Next Steps** — what's incomplete, what you'd improve with more time, and any known weak spots (e.g., new-SKU accuracy)

## Before You Ship, Verify

- [ ] Every SKU loads and displays without error, including the 3 new ones
- [ ] At least one established SKU and the sparse-history handling for new SKUs each produce a sensible flag (or a sensible "not enough data yet")
- [ ] A flagged SKU's explanation cites numbers that actually match its row in the data — spot-check at least two
- [ ] The question box answers at least two different free-text questions, grounded in retrieved data, not generic text
- [ ] The README is something a business stakeholder or another engineer could act on without talking to you
- [ ] The app is live at a public URL and works when opened cold
