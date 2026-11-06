"""
Streamlit Web Application
Agricultural Commodity Price Monitoring and Tracking System for Tamil Nadu Vegetable Markets.
Provides multi-market price exploration, comparison, trend analysis, change tracking,
scrape run auditing, and ethical source compliance controls.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone
from pathlib import Path
import html

import config
import database as db
import scraper
import scheduler

# Page configuration
st.set_page_config(
    page_title="TN Agri Price Tracker | Monitoring & Tracking",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Agricultural theme with crisp readable typography)
st.markdown("""
<style>
    :root {
        --agri-green: #2e7d32;
        --agri-dark-green: #1b5e20;
        --agri-light-green: #e8f5e9;
        --agri-accent: #4caf50;
        --neutral-bg: #f9fafb;
    }
    .main-header {
        background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%);
        padding: 22px 28px;
        border-radius: 10px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.06);
    }
    .main-header h1 {
        margin: 0;
        font-size: 26px;
        font-weight: 700;
        color: white !important;
    }
    .main-header p {
        margin: 6px 0 0 0;
        font-size: 14px;
        opacity: 0.92;
        color: #e8f5e9 !important;
    }
    .badge-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .badge-partial { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .badge-failed { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .badge-info { background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
    .metric-card {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-left: 4px solid #2e7d32;
        padding: 16px 20px;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .caution-box {
        background-color: #fffde7;
        border-left: 4px solid #fbc02d;
        padding: 14px 18px;
        border-radius: 6px;
        font-size: 13px;
        color: #5d4037;
        margin: 16px 0;
    }
</style>
""", unsafe_allow_html=True)

# Ensure Database is Initialized
db.init_db()

# ---------------------------------------------------------
# Sidebar Navigation & Operational Status
# ---------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/harvest.png", width=64)
    st.title("Agri Price Tracker")
    st.caption("Tamil Nadu Vegetable Markets System")
    
    st.markdown("---")
    navigation = st.radio(
        "Navigation",
        [
            "🌾 Overview & KPIs",
            "📊 Vegetable Market Prices",
            "⚖️ Market Price Comparison",
            "📈 Historical Price Trends",
            "🔄 Change Tracker & Audit",
            "📋 Data Collection & Runs",
            "⚙️ Source Approval & Settings"
        ],
        index=0
    )
    
    st.markdown("---")
    st.subheader("Data Source Status")
    if config.MENTOR_LIVE_COLLECTION_APPROVED:
        st.markdown('<span class="badge-pill badge-success">LIVE API: APPROVED</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-pill badge-partial">OFFLINE FIXTURE MODE</span>', unsafe_allow_html=True)
        st.caption("🔒 Live scraping locked pending mentor checkpoint signoff.")

    st.markdown("---")
    st.subheader("Quick Actions")
    if st.button("⚡ Quick Refresh (Cycle 2)", use_container_width=True):
        adapter = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=2)
        res = adapter.run_pipeline()
        st.toast(f"Refresh completed: {res['status']} ({res['records_inserted']} inserted, {res['records_updated']} updated)", icon="✅")
        st.rerun()

# Top Header Banner
st.markdown("""
<div class="main-header">
    <h1>Agricultural Commodity Price Monitoring and Tracking System</h1>
    <p>Tamil Nadu Mandi & Uzhavar Sandhai Daily Price Intelligence (Agmarknet / OGD India Standards)</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# 1. OVERVIEW & KPIS
# ---------------------------------------------------------
if navigation == "🌾 Overview & KPIs":
    st.subheader("Market Price Surveillance Overview")
    
    stats = db.get_summary_stats()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Records Tracked", stats["total_records"])
    with col2:
        st.metric("Tamil Nadu Markets", stats["total_markets"])
    with col3:
        st.metric("Vegetables Monitored", stats["total_commodities"])
    with col4:
        st.metric("Price Updates Detected", stats["updated_count"])
    with col5:
        st.metric("Newly Discovered", stats["new_count"])

    st.markdown("---")

    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.subheader("Collection Freshness & Run Status")
        last_success = stats["last_success_run"]
        latest_run = stats["latest_run"]
        
        if last_success:
            finish_time = last_success["finish_time"]
            dt_finish = datetime.fromisoformat(finish_time.replace("Z", "+00:00"))
            hours_elapsed = round((datetime.now(timezone.utc) - dt_finish).total_seconds() / 3600.0, 1)
            
            freshness_badge = "badge-success" if hours_elapsed < config.STALE_DATA_THRESHOLD_HOURS else "badge-failed"
            freshness_text = "FRESH (< 48 hrs)" if hours_elapsed < config.STALE_DATA_THRESHOLD_HOURS else "STALE (>= 48 hrs)"
            
            st.markdown(f"""
            <div class="metric-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <h4 style="margin:0; color:#1b5e20;">Last Successful Collection</h4>
                        <p style="margin:4px 0 0 0; color:#555;"><b>Run ID:</b> <code>{last_success['run_id']}</code></p>
                        <p style="margin:4px 0 0 0; color:#555;"><b>Timestamp:</b> {dt_finish.strftime('%Y-%m-%d %H:%M:%S UTC')} ({hours_elapsed}h ago)</p>
                        <p style="margin:4px 0 0 0; color:#555;"><b>Source Mode:</b> {last_success['source_mode']}</p>
                    </div>
                    <div>
                        <span class="badge-pill {freshness_badge}">{freshness_text}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No successful runs logged yet. Execute an ingestion cycle from 'Data Collection & Runs'.")

        if latest_run and latest_run["status"] in ("PARTIAL", "FAILED"):
            st.warning(f"⚠️ Latest Run Notice: Status '{latest_run['status']}'. Details: {latest_run.get('error_details', 'N/A')}")

        st.subheader("Data Integrity & Duplicate Prevention Guarantee")
        st.write("""
        - **Deterministic Fingerprinting:** Every record uses a SHA-256 content hash across all price attributes to isolate genuine market shifts from redundant data.
        - **Composite Key Invariance:** Records are keyed uniquely on `(commodity, market, district, price_unit)`. Repeated runs never inflate total records.
        - **Audit Trail:** Every detected price variation creates an immutable timestamped entry in `price_history`.
        """)

    with col_right:
        st.subheader("Vegetable Distribution")
        records = db.get_all_records()
        if records:
            df = pd.DataFrame(records)
            comm_counts = df["commodity"].value_counts().reset_index()
            comm_counts.columns = ["Commodity", "Market Count"]
            fig = px.pie(
                comm_counts,
                names="Commodity",
                values="Market Count",
                hole=0.45,
                color_discrete_sequence=px.colors.sequential.Greens_r
            )
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No records to visualize.")


# ---------------------------------------------------------
# 2. VEGETABLE MARKET PRICES (EXPLORER)
# ---------------------------------------------------------
elif navigation == "📊 Vegetable Market Prices":
    st.subheader("Tamil Nadu Vegetable Market Price Explorer")
    st.caption("Filter, search, inspect price spreads, and export records for research.")

    records = db.get_all_records()
    if not records:
        st.warning("No price records currently stored. Please trigger an ingestion run.")
    else:
        df = pd.DataFrame(records)
        
        # Filter controls
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            all_commodities = ["All"] + sorted(df["commodity"].unique().tolist())
            sel_comm = st.selectbox("Filter Commodity", all_commodities)
        with f_col2:
            all_districts = ["All"] + sorted(df["district"].unique().tolist())
            sel_dist = st.selectbox("Filter District", all_districts)
        with f_col3:
            filtered_df = df
            if sel_dist != "All":
                filtered_df = filtered_df[filtered_df["district"] == sel_dist]
            all_markets = ["All"] + sorted(filtered_df["market"].unique().tolist())
            sel_market = st.selectbox("Filter Market", all_markets)
        with f_col4:
            search_query = st.text_input("Search (keyword)", placeholder="e.g. Koyambedu")

        # Apply filtering
        result_df = df.copy()
        if sel_comm != "All":
            result_df = result_df[result_df["commodity"] == sel_comm]
        if sel_dist != "All":
            result_df = result_df[result_df["district"] == sel_dist]
        if sel_market != "All":
            result_df = result_df[result_df["market"] == sel_market]
        if search_query:
            q = search_query.lower()
            result_df = result_df[
                result_df["commodity"].str.lower().str.contains(q) |
                result_df["market"].str.lower().str.contains(q) |
                result_df["district"].str.lower().str.contains(q)
            ]

        st.write(f"Showing **{len(result_df)}** of **{len(df)}** vegetable price records:")
        
        # Format table presentation
        display_df = result_df[[
            "commodity", "market", "district", "reporting_date",
            "min_price", "max_price", "modal_price", "price_unit",
            "change_status", "last_successful_observation"
        ]].copy()
        
        display_df.rename(columns={
            "commodity": "Commodity",
            "market": "Market",
            "district": "District",
            "reporting_date": "Report Date",
            "min_price": "Min (₹)",
            "max_price": "Max (₹)",
            "modal_price": "Modal (₹)",
            "price_unit": "Unit",
            "change_status": "Status",
            "last_successful_observation": "Last Observed (UTC)"
        }, inplace=True)
        
        st.dataframe(
            display_df.style.format({
                "Min (₹)": "{:,.2f}",
                "Max (₹)": "{:,.2f}",
                "Modal (₹)": "{:,.2f}"
            }),
            use_container_width=True,
            height=460
        )
        
        # CSV Export
        csv_data = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Filtered Records as CSV",
            data=csv_data,
            file_name=f"tn_agri_prices_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )


# ---------------------------------------------------------
# 3. MARKET COMPARISON
# ---------------------------------------------------------
elif navigation == "⚖️ Market Price Comparison":
    st.subheader("Inter-Market Vegetable Price Comparison")
    st.caption("Compare modal, minimum, and maximum prices for identical vegetables across Tamil Nadu markets.")

    # Critical Economic Disclaimer (as mandated by SRS)
    st.markdown("""
    <div class="caution-box">
        ⚠️ <b>Economic & Trader Advisory Note:</b> A lower or higher reported mandi modal price does not automatically imply the best selling or buying net arbitrage. 
        True net realizations for farmers and traders must account for inter-district transportation costs, loading/unloading, quality grading (Grade A vs B/C), APMC market cess, agent commission fees, and transit perishability.
    </div>
    """, unsafe_allow_html=True)

    records = db.get_all_records()
    if not records:
        st.warning("No records to compare.")
    else:
        df = pd.DataFrame(records)
        commodities = sorted(df["commodity"].unique().tolist())
        
        c_col1, c_col2 = st.columns([2, 2])
        with c_col1:
            selected_veg = st.selectbox("Select Vegetable for Multi-Market Comparison", commodities, index=0)
        with c_col2:
            selected_unit = st.selectbox("Price Unit", [config.DEFAULT_PRICE_UNIT])

        comp_df = df[(df["commodity"] == selected_veg) & (df["price_unit"] == selected_unit)]
        
        if comp_df.empty:
            st.info(f"No price records found for {selected_veg}.")
        else:
            comp_df = comp_df.sort_values(by="modal_price", ascending=True)
            
            # Plotly Grouped Bar Chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=comp_df["market"] + " (" + comp_df["district"] + ")",
                y=comp_df["min_price"],
                name="Min Price (₹)",
                marker_color="#81c784"
            ))
            fig.add_trace(go.Bar(
                x=comp_df["market"] + " (" + comp_df["district"] + ")",
                y=comp_df["modal_price"],
                name="Modal Price (₹)",
                marker_color="#2e7d32"
            ))
            fig.add_trace(go.Bar(
                x=comp_df["market"] + " (" + comp_df["district"] + ")",
                y=comp_df["max_price"],
                name="Max Price (₹)",
                marker_color="#1b5e20"
            ))

            fig.update_layout(
                title=f"Price Distribution for {selected_veg} across Tamil Nadu Markets ({selected_unit})",
                barmode='group',
                xaxis_title="Market (District)",
                yaxis_title=f"Price ({selected_unit})",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=450
            )
            st.plotly_chart(fig, use_container_width=True)

            # Spread Table
            st.write("Detailed Mandi Price Breakdown:")
            st.dataframe(
                comp_df[[
                    "market", "district", "reporting_date", "min_price", "modal_price", "max_price", "price_unit"
                ]].rename(columns={
                    "market": "Market",
                    "district": "District",
                    "reporting_date": "Date",
                    "min_price": "Min (₹)",
                    "modal_price": "Modal (₹)",
                    "max_price": "Max (₹)",
                    "price_unit": "Unit"
                }).style.format({
                    "Min (₹)": "{:,.2f}",
                    "Modal (₹)": "{:,.2f}",
                    "Max (₹)": "{:,.2f}"
                }),
                use_container_width=True
            )


# ---------------------------------------------------------
# 4. HISTORICAL PRICE TRENDS
# ---------------------------------------------------------
elif navigation == "📈 Historical Price Trends":
    st.subheader("Historical Price Trends & Volatility Tracking")
    st.caption("Visualizing longitudinal price movement across recorded reporting dates.")

    records = db.get_all_records()
    if not records:
        st.warning("No records found.")
    else:
        df = pd.DataFrame(records)
        commodities = sorted(df["commodity"].unique().tolist())
        
        t_col1, t_col2, t_col3 = st.columns(3)
        with t_col1:
            sel_comm = st.selectbox("Select Commodity", commodities)
        with t_col2:
            districts = ["All"] + sorted(df[df["commodity"] == sel_comm]["district"].unique().tolist())
            sel_dist = st.selectbox("Select District", districts)
        with t_col3:
            price_measure = st.selectbox("Price Measure", ["Modal Price", "Min Price", "Max Price", "All Spread"])

        trend_data = db.get_historical_trends(sel_comm, district=sel_dist)
        
        if not trend_data:
            st.info(f"Insufficient trend observations recorded for {sel_comm}. Ingest subsequent refresh cycles to see trajectory.")
        else:
            tdf = pd.DataFrame(trend_data)
            
            fig = go.Figure()
            markets = tdf["market"].unique().tolist()
            
            for mkt in markets:
                sub = tdf[tdf["market"] == mkt].sort_values(by="reporting_date")
                
                if price_measure == "Modal Price":
                    fig.add_trace(go.Scatter(
                        x=sub["reporting_date"],
                        y=sub["modal_price"],
                        mode='lines+markers',
                        name=f"{mkt} (Modal)"
                    ))
                elif price_measure == "Min Price":
                    fig.add_trace(go.Scatter(
                        x=sub["reporting_date"],
                        y=sub["min_price"],
                        mode='lines+markers',
                        name=f"{mkt} (Min)"
                    ))
                elif price_measure == "Max Price":
                    fig.add_trace(go.Scatter(
                        x=sub["reporting_date"],
                        y=sub["max_price"],
                        mode='lines+markers',
                        name=f"{mkt} (Max)"
                    ))
                else:  # All Spread
                    fig.add_trace(go.Scatter(
                        x=sub["reporting_date"],
                        y=sub["modal_price"],
                        mode='lines+markers',
                        name=f"{mkt} (Modal)"
                    ))

            fig.update_layout(
                title=f"Price Trend: {sel_comm} across Tamil Nadu Mandis (Reporting Dates)",
                xaxis_title="Reporting Date",
                yaxis_title="Price (Rs/Quintal)",
                hovermode="x unified",
                height=480
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("View Raw Trend Observation Points"):
                st.dataframe(tdf, use_container_width=True)


# ---------------------------------------------------------
# 5. CHANGE TRACKER & AUDIT
# ---------------------------------------------------------
elif navigation == "🔄 Change Tracker & Audit":
    st.subheader("Price Change Audit Trail & State Transitions")
    st.caption("Immutable log of price shifts, initial observations, and verification events.")

    history_entries = db.get_price_history(limit=150)
    
    if not history_entries:
        st.info("No change history recorded yet.")
    else:
        hdf = pd.DataFrame(history_entries)
        
        # Summary counts
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total History Events", len(hdf))
        with c2:
            st.metric("Price Fluctuation Events", len(hdf[hdf["change_type"] == "PRICE_CHANGE"]))
        with c3:
            st.metric("Initial Record Discoveries", len(hdf[hdf["change_type"] == "INITIAL"]))

        st.markdown("---")
        
        # Filter by commodity
        commodities_in_hist = ["All"] + sorted(hdf["commodity"].unique().tolist())
        sel_hist_comm = st.selectbox("Filter History by Commodity", commodities_in_hist)
        
        if sel_hist_comm != "All":
            hdf = hdf[hdf["commodity"] == sel_hist_comm]

        display_hist = hdf[[
            "commodity", "market", "district", "reporting_date",
            "change_type", "prev_modal_price", "new_modal_price",
            "observed_at", "run_id", "details"
        ]].copy()

        display_hist.rename(columns={
            "commodity": "Commodity",
            "market": "Market",
            "district": "District",
            "reporting_date": "Report Date",
            "change_type": "Event Type",
            "prev_modal_price": "Previous Modal (₹)",
            "new_modal_price": "New Modal (₹)",
            "observed_at": "Observed At (UTC)",
            "run_id": "Run ID",
            "details": "Change Explanation"
        }, inplace=True)

        st.dataframe(
            display_hist.style.format({
                "Previous Modal (₹)": lambda x: f"{x:,.2f}" if pd.notnull(x) else "-",
                "New Modal (₹)": lambda x: f"{x:,.2f}" if pd.notnull(x) else "-"
            }),
            use_container_width=True,
            height=500
        )


# ---------------------------------------------------------
# 6. DATA COLLECTION & LOGS
# ---------------------------------------------------------
elif navigation == "📋 Data Collection & Runs":
    st.subheader("Data Collection Audit Logs & Ingestion Controller")
    st.caption("Inspect pipeline executions, verify deduplication, and trigger controlled refreshes.")

    # Ingestion Controls
    st.markdown("### Manual Collection Trigger")
    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    
    with tcol1:
        if st.button("▶️ Run Cycle 1 (Baseline)", use_container_width=True):
            with st.spinner("Ingesting Cycle 1..."):
                adapter = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=1)
                res = adapter.run_pipeline()
                st.success(f"Cycle 1 complete: {res['status']}. Inserted: {res['records_inserted']}")
                st.rerun()

    with tcol2:
        if st.button("▶️ Run Cycle 2 (Updates)", use_container_width=True):
            with st.spinner("Ingesting Cycle 2..."):
                adapter = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=2)
                res = adapter.run_pipeline()
                st.success(f"Cycle 2 complete: {res['status']}. Updated: {res['records_updated']}, Inserted: {res['records_inserted']}")
                st.rerun()

    with tcol3:
        if st.button("▶️ Run Cycle 3 (Malformed Test)", use_container_width=True):
            with st.spinner("Ingesting Cycle 3 with intentional error rows..."):
                adapter = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=3)
                res = adapter.run_pipeline()
                st.warning(f"Cycle 3 complete: {res['status']}. Updated: {res['records_updated']}, Failed/Isolated: {res['records_failed']}")
                st.rerun()

    with tcol4:
        if st.button("▶️ Run Synthetic Simulation", use_container_width=True):
            with st.spinner("Generating synthetic market bulletin..."):
                adapter = scraper.get_adapter(config.SourceMode.SYNTHETIC_DEV, price_drift_pct=0.03)
                res = adapter.run_pipeline()
                st.info(f"Synthetic run: {res['status']}. Updated: {res['records_updated']}, Inserted: {res['records_inserted']}")
                st.rerun()

    st.markdown("---")
    st.subheader("Scrape Run History Audit")
    
    runs = db.get_scrape_runs(limit=30)
    if not runs:
        st.info("No runs recorded.")
    else:
        rdf = pd.DataFrame(runs)
        
        display_runs = rdf[[
            "run_id", "status", "source_mode", "start_time", "finish_time",
            "records_found", "records_inserted", "records_updated", "records_failed", "error_details"
        ]].copy()
        
        display_runs.rename(columns={
            "run_id": "Run ID",
            "status": "Status",
            "source_mode": "Source Mode",
            "start_time": "Start (UTC)",
            "finish_time": "Finish (UTC)",
            "records_found": "Found",
            "records_inserted": "Inserted",
            "records_updated": "Updated",
            "records_failed": "Failed",
            "error_details": "Error Log"
        }, inplace=True)
        
        st.dataframe(display_runs, use_container_width=True, height=360)


# ---------------------------------------------------------
# 7. SOURCE APPROVAL & SETTINGS
# ---------------------------------------------------------
elif navigation == "⚙️ Source Approval & Settings":
    st.subheader("Data Source Governance & Mentor Acceptance")
    st.caption("SRS Compliance, Legal/Ethical Guidelines, and Adapter Configuration.")

    st.markdown("""
    ### Mentor Checkpoint Review Matrix (Cybernaut SRS)
    """)

    checkpoints = [
        {
            "Checkpoint": "CP-1: Source Alternatives & Approval",
            "Requirement": "Evaluate Agmarknet vs OGD Data.gov.in API vs TNAU. Document terms & robots.txt",
            "Status": "COMPLETED & DOCUMENTED",
            "Notes": "Agmarknet evaluated; Data.gov.in official REST API identified as preferred legal channel."
        },
        {
            "Checkpoint": "CP-2: 10 Reviewed Records & Dictionary",
            "Requirement": "Baseline prototype with 10 verified records and standardized schema",
            "Status": "COMPLETED",
            "Notes": "Configured across 34+ authentic Tamil Nadu records with field validation."
        },
        {
            "Checkpoint": "CP-3: Deduplicated Database Pipeline",
            "Requirement": "Repeatable SQLite ingestion without duplicate records",
            "Status": "COMPLETED & VERIFIED",
            "Notes": "Verified: rerun of identical cycle yields 0 new insertions, 100% unchanged."
        },
        {
            "Checkpoint": "CP-4: Three Refresh Cycles",
            "Requirement": "Demonstrate baseline, price change updates, and error isolation",
            "Status": "COMPLETED & TESTED",
            "Notes": "Cycles 1, 2, and 3 built and tested via Pytest test_offline_three_refresh_cycles."
        },
        {
            "Checkpoint": "CP-5: Challenge & Malformed Records",
            "Requirement": "Isolate malformed rows and altered schema without pipeline crash",
            "Status": "COMPLETED",
            "Notes": "Tested with inverted prices, corrupt text, and missing table schema."
        },
        {
            "Checkpoint": "CP-6: Source Ethics & Git Governance",
            "Requirement": "No CAPTCHA bypass, request limits, backoff, complete docs",
            "Status": "COMPLETED",
            "Notes": "Live scraper locked behind MENTOR_LIVE_COLLECTION_APPROVED safeguard."
        }
    ]
    st.table(pd.DataFrame(checkpoints))

    st.markdown("---")
    st.subheader("Live Collection Authorization Safeguard")
    
    st.write(f"**Mentor Approval Status:** `{'APPROVED' if config.MENTOR_LIVE_COLLECTION_APPROVED else 'PENDING MENTOR SIGN-OFF'}`")
    
    if not config.MENTOR_LIVE_COLLECTION_APPROVED:
        st.error(f"🔒 **Live Scraping Guardrail Active:** {config.SOURCE_APPROVAL_BLOCKER_REASON}")
        st.info("""
        **Steps Required to Unlock Live Collection:**
        1. Obtain an API key from https://data.gov.in/ (Resource: Daily Mandi Prices under NDSAP).
        2. Set environment variable `DATAGOVIN_API_KEY` or enter key below.
        3. Confirm Agmarknet crawl-delay policy with project mentor.
        4. Toggle `MENTOR_LIVE_COLLECTION_APPROVED = True` in `config.py`.
        """)

    st.markdown("---")
    st.subheader("Configured Tamil Nadu Commodities & Mandis")
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        st.write("**Monitored Commodities:**")
        st.write(", ".join(config.CONFIGURED_COMMODITIES))
    with c_col2:
        st.write("**Monitored Markets:**")
        for m in config.CONFIGURED_MARKETS:
            st.write(f"- {m['market']} (*{m['district']}*)")
