import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import duckdb
import json
import warnings
warnings.filterwarnings('ignore')
 
# ─────────────────────────────────────
# CONFIG
# ─────────────────────────────────────
st.set_page_config(
    page_title  = "E-Commerce Analytics",
    page_icon   = "🛒",
    layout      = "wide"
)
 
# ─────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────
@st.cache_resource          # ← use cache_resource (not cache_data) for DB connections
def get_connection():
    con = duckdb.connect('data/olist.duckdb')
    con.execute("CREATE OR REPLACE VIEW delivered AS SELECT * FROM read_parquet('data/delivered_orders.parquet')")
    con.execute("CREATE OR REPLACE VIEW master   AS SELECT * FROM read_parquet('data/master_orders.parquet')")
    return con
 
@st.cache_data              # ← cache_data is fine for plain DataFrames
def load_dataframes():
    con = get_connection()
    delivered   = con.execute("SELECT * FROM delivered").df()
    master      = con.execute("SELECT * FROM master").df()
    rfm         = pd.read_csv('data/rfm_scores.csv')
    seg_summary = pd.read_csv('data/rfm_segment_summary.csv')
    actions     = pd.read_csv('data/rfm_action_matrix.csv')
    return delivered, master, rfm, seg_summary, actions
 
con                                          = get_connection()
delivered, master, rfm, seg_summary, actions = load_dataframes()
 
# ─────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────
st.sidebar.image("https://img.icons8.com/color/96/shopping-cart.png", width=55)
st.sidebar.title("E-Commerce Analytics")
st.sidebar.markdown("---")
 
page = st.sidebar.radio("Navigate", [
    "📊 Overview",
    "🔻 Funnel Analysis",
    "🧪 A/B Test Results",
    "👥 Customer Segments",
    "📦 Delivery & Reviews"
])
 
st.sidebar.markdown("---")
st.sidebar.markdown("**Dataset:** Olist Brazilian E-Commerce")
st.sidebar.markdown("**Orders:** ~100K transactions")
st.sidebar.markdown("**Period:** 2017 – 2018")
st.sidebar.markdown("**Tool:** DuckDB + Streamlit")
 
# ─────────────────────────────────────
# PAGE 1: OVERVIEW
# ─────────────────────────────────────
if page == "📊 Overview":
    st.title("📊 Business Overview")
    st.markdown("Top-line metrics across the full dataset.")
    st.markdown("---")
 
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Orders",
              f"{len(delivered):,}")
    c2.metric("Total Revenue",
              f"R${delivered['total_payment'].sum()/1e6:.1f}M")
    c3.metric("Avg Order Value",
              f"R${delivered['total_payment'].mean():.2f}")
    c4.metric("Avg Delivery",
              f"{delivered['delivery_days'].mean():.1f} days")
    c5.metric("Avg Review Score",
              f"{delivered['review_score'].mean():.2f} / 5")
 
    st.markdown("---")
 
    col1, col2 = st.columns(2)
 
    with col1:
        monthly = (delivered
            .groupby('yearmon')['total_payment']
            .sum().reset_index())
        fig = px.line(monthly, x='yearmon', y='total_payment',
                      title='Monthly Revenue Trend',
                      labels={'total_payment':'Revenue (R$)',
                              'yearmon':'Month'},
                      color_discrete_sequence=['#378ADD'])
        fig.update_traces(fill='tozeroy', fillcolor='rgba(55,138,221,0.1)')
        st.plotly_chart(fig, use_container_width=True)
 
    with col2:
        translations = {
            'beleza_saude'          :'Health & Beauty',
            'informatica_acessorios':'Computer Accessories',
            'automotivo'            :'Automotive',
            'cama_mesa_banho'       :'Bed & Bath',
            'moveis_decoracao'      :'Furniture & Decor',
            'esporte_lazer'         :'Sports & Leisure',
            'utilidades_domesticas' :'Home Appliances',
            'relogios_presentes'    :'Watches & Gifts',
        }
        cat_rev = (delivered
            .groupby('primary_category')['total_payment']
            .sum().nlargest(8).reset_index())
        cat_rev['category'] = (cat_rev['primary_category']
            .map(translations)
            .fillna(cat_rev['primary_category']))
        fig2 = px.bar(cat_rev.sort_values('total_payment'),
                      x='total_payment', y='category',
                      orientation='h',
                      title='Top 8 Categories by Revenue',
                      color_discrete_sequence=['#1D9E75'],
                      labels={'total_payment':'Revenue (R$)',
                              'category':'Category'})
        st.plotly_chart(fig2, use_container_width=True)
 
    # State revenue map (bubble)
    state_rev = (delivered
        .groupby('customer_state')['total_payment']
        .sum().reset_index()
        .sort_values('total_payment', ascending=False))
    fig3 = px.bar(state_rev.head(10),
                  x='customer_state', y='total_payment',
                  title='Revenue by State (Top 10)',
                  color='total_payment',
                  color_continuous_scale='Blues',
                  labels={'total_payment':'Revenue (R$)',
                          'customer_state':'State'})
    st.plotly_chart(fig3, use_container_width=True)
 
# ─────────────────────────────────────
# PAGE 2: FUNNEL
# ─────────────────────────────────────
elif page == "🔻 Funnel Analysis":
    st.title("🔻 Conversion Funnel Analysis")
    st.markdown("Order lifecycle from placement to delivery.")
    st.markdown("---")
 
    # Build funnel from master
    total     = len(master)
    approved  = len(master[~master['order_status'].isin(['canceled','unavailable'])])
    shipped   = master['shipped_at'].notna().sum()
    delivered_n = master['delivered_at'].notna().sum()
 
    stages  = ['Placed','Approved','Shipped','Delivered']
    counts  = [total, approved, shipped, delivered_n]
    revs    = [
        master['total_payment'].sum(),
        master[~master['order_status'].isin(['canceled','unavailable'])]['total_payment'].sum(),
        master[master['shipped_at'].notna()]['total_payment'].sum(),
        master[master['delivered_at'].notna()]['total_payment'].sum()
    ]
 
    col1, col2 = st.columns(2)
 
    with col1:
        fig = go.Figure(go.Funnel(
            y = stages,
            x = counts,
            textinfo = "value+percent initial",
            marker   = dict(color=['#378ADD','#1D9E75',
                                   '#7F77DD','#BA7517'])
        ))
        fig.update_layout(title='Order Volume Funnel')
        st.plotly_chart(fig, use_container_width=True)
 
    with col2:
        fig2 = go.Figure(go.Funnel(
            y = stages,
            x = [r/1e6 for r in revs],
            texttemplate = "R$%{x:.1f}M",
            marker = dict(color=['#378ADD','#1D9E75',
                                 '#7F77DD','#BA7517'])
        ))
        fig2.update_layout(title='Revenue Funnel (R$ Millions)')
        st.plotly_chart(fig2, use_container_width=True)
 
    st.markdown("---")
    st.subheader("Drop-off Impact")
 
    drop_data = pd.DataFrame({
        'Transition'    : ['Placed → Approved',
                           'Approved → Shipped',
                           'Shipped → Delivered'],
        'Orders Lost'   : [total-approved,
                           approved-shipped,
                           shipped-delivered_n],
        'Revenue Lost'  : [revs[0]-revs[1],
                           revs[1]-revs[2],
                           revs[2]-revs[3]]
    })
    drop_data['Revenue Lost'] = drop_data['Revenue Lost'].map('R${:,.0f}'.format)
    st.dataframe(drop_data, use_container_width=True)
 
    # Cohort heatmap
    st.markdown("---")
    st.subheader("Cohort Retention Heatmap")
    st.markdown("% of customers from each cohort who return each month.")
 
    cohort_raw = con.execute("""
        WITH fp AS (
            SELECT customer_id,
                   MIN(DATE_TRUNC('month', purchased_at)) AS cohort_month
            FROM delivered GROUP BY customer_id
        ),
        tagged AS (
            SELECT d.customer_id, fp.cohort_month,
                   DATEDIFF('month', fp.cohort_month,
                       DATE_TRUNC('month', d.purchased_at)) AS period
            FROM delivered d JOIN fp ON d.customer_id = fp.customer_id
        )
        SELECT STRFTIME(cohort_month,'%Y-%m') AS cohort,
               period,
               COUNT(DISTINCT customer_id) AS customers
        FROM tagged
        GROUP BY cohort, period
        ORDER BY cohort, period
    """).df()
 
    pivot = (cohort_raw
        .pivot_table(index='cohort', columns='period',
                     values='customers', aggfunc='sum'))
 
    # Guard: only plot if repeat purchase data exists
    if pivot.shape[1] > 1:
        retention  = (pivot.divide(pivot.iloc[:, 0], axis=0) * 100).round(1)
        plot_ret   = retention.iloc[-12:, :10]
        fig3 = px.imshow(plot_ret,
                         color_continuous_scale='YlOrRd_r',
                         title='Cohort Retention Heatmap (%)',
                         labels={'x':'Months Since First Purchase',
                                 'y':'Cohort','color':'Retention %'},
                         zmin=0, zmax=100,
                         text_auto=True)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info(
            "📊 **Cohort Retention — Not Applicable**\n\n"
            "This dataset (Olist) has one order per customer, so there are "
            "no repeat purchases to plot. This is a known characteristic of "
            "the dataset, not a data error. The RFM segmentation on the "
            "Customer Segments page is the appropriate analysis for this data."
        )
 
# ─────────────────────────────────────
# PAGE 3: A/B TEST
# ─────────────────────────────────────
elif page == "🧪 A/B Test Results":
    st.title("🧪 A/B Test — Checkout Experience")
    st.markdown("---")
 
    ab = master[
        master['payment_type'].isin(['credit_card','debit_card','voucher']) &
        master['total_payment'].notna()
    ].copy()
    ab['ab_group']    = ab['payment_type'].apply(
        lambda x: 'Control (Credit)' if x == 'credit_card' else 'Treatment (Debit/Voucher)')
    ab['is_cancelled'] = ab['order_status'].isin(
        ['canceled','unavailable']).astype(int)
 
    ctrl = ab[ab['ab_group'] == 'Control (Credit)']
    trt  = ab[ab['ab_group'] == 'Treatment (Debit/Voucher)']
 
    rate_c = ctrl['is_cancelled'].mean()
    rate_t = trt['is_cancelled'].mean()
 
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Control size",  f"{len(ctrl):,}")
    c2.metric("Treatment size",f"{len(trt):,}")
    c3.metric("Control cancel rate",   f"{rate_c*100:.3f}%")
    c4.metric("Treatment cancel rate", f"{rate_t*100:.3f}%",
              f"{(rate_t-rate_c)*100:+.3f} pp",
              delta_color="inverse")
 
    st.markdown("---")
    col1, col2 = st.columns(2)
 
    with col1:
        fig = go.Figure(data=[
            go.Bar(name='Cancellation Rate %',
                   x=['Control','Treatment'],
                   y=[rate_c*100, rate_t*100],
                   marker_color=['#378ADD','#1D9E75'],
                   text=[f'{rate_c*100:.3f}%',
                         f'{rate_t*100:.3f}%'],
                   textposition='outside')
        ])
        fig.update_layout(title='Cancellation Rate by Group',
                          yaxis_title='Cancellation Rate (%)')
        st.plotly_chart(fig, use_container_width=True)
 
    with col2:
        rev_ctrl = ctrl['review_score'].mean()
        rev_trt  = trt['review_score'].mean()
        fig2 = go.Figure(data=[
            go.Bar(name='Avg Review',
                   x=['Control','Treatment'],
                   y=[rev_ctrl, rev_trt],
                   marker_color=['#378ADD','#1D9E75'],
                   text=[f'{rev_ctrl:.3f}', f'{rev_trt:.3f}'],
                   textposition='outside')
        ])
        fig2.update_layout(title='Avg Review Score by Group',
                           yaxis=dict(range=[3.5,4.5]),
                           yaxis_title='Avg Review Score')
        st.plotly_chart(fig2, use_container_width=True)
 
    # ROI simulator
    st.markdown("---")
    st.subheader("Revenue Uplift Simulator")
    avg_val = ab['total_payment'].mean()
    monthly = st.slider("Monthly orders", 5000, 30000, 10000, 500)
    monthly_uplift = monthly * (rate_c - rate_t) * avg_val
 
    st.info(f"At **{monthly:,} orders/month**, recovering the cancellation "
            f"gap generates **R${monthly_uplift:,.0f}/month** "
            f"(R${monthly_uplift*12:,.0f}/year) in additional revenue.")
 
# ─────────────────────────────────────
# PAGE 4: CUSTOMER SEGMENTS
# ─────────────────────────────────────
elif page == "👥 Customer Segments":
    st.title("👥 RFM Customer Segmentation")
    st.markdown("---")
 
    seg_colors = {
        'Champions'      :'#1D9E75',
        'Loyal'          :'#378ADD',
        'Promising'      :'#7F77DD',
        'At Risk'        :'#F5A623',
        'Need Attention' :'#BA7517',
        'Cant Lose Them' :'#D85A30',
        'Lost'           :'#AAAAAA'
    }
 
    c1,c2,c3 = st.columns(3)
    c1.metric("Total Customers Scored", f"{len(rfm):,}")
    c2.metric("Champions",
              f"{(rfm['segment']=='Champions').sum():,}",
              f"{(rfm['segment']=='Champions').mean()*100:.1f}% of base")
    c3.metric("At-Risk / Lost",
              f"{rfm['segment'].isin(['At Risk','Lost','Cant Lose Them']).sum():,}",
              "Need immediate action",
              delta_color="inverse")
 
    st.markdown("---")
    col1, col2 = st.columns(2)
 
    with col1:
        fig = px.bar(seg_summary.sort_values('total_revenue', ascending=True),
                     x='total_revenue', y='segment',
                     orientation='h',
                     title='Revenue by Segment',
                     color='segment',
                     color_discrete_map=seg_colors,
                     text='pct_revenue',
                     labels={'total_revenue':'Total Revenue (R$)',
                             'segment':'Segment'})
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
 
    with col2:
        fig2 = px.scatter(rfm.sample(min(5000, len(rfm))),
                          x='recency_days', y='monetary',
                          color='segment',
                          color_discrete_map=seg_colors,
                          title='Recency vs Monetary Value',
                          opacity=0.5,
                          labels={'recency_days':'Days Since Last Purchase',
                                  'monetary':'Total Spend (R$)'})
        st.plotly_chart(fig2, use_container_width=True)
 
    # Action matrix
    st.markdown("---")
    st.subheader("Segment Action Recommendations")
    for _, row in actions.iterrows():
        color = seg_colors.get(row['segment'],'#888')
        st.markdown(
            f"<div style='border-left: 4px solid {color};"
            f"padding: 8px 16px; margin: 6px 0;"
            f"background: var(--background-color);"
            f"border-radius: 0 8px 8px 0'>"
            f"<strong>{row['segment']}</strong> &nbsp;·&nbsp; "
            f"{row['customers']:,} customers &nbsp;·&nbsp; "
            f"Avg spend R${row['avg_spend']:,.0f}<br>"
            f"<span style='color: #888; font-size: 13px'>"
            f"{row['action']}</span></div>",
            unsafe_allow_html=True
        )
 
# ─────────────────────────────────────
# PAGE 5: DELIVERY & REVIEWS
# ─────────────────────────────────────
elif page == "📦 Delivery & Reviews":
    st.title("📦 Delivery Performance & Reviews")
    st.markdown("---")
 
    c1,c2,c3 = st.columns(3)
    on_time = (delivered['delivery_delta'] <= 0).mean() * 100
    c1.metric("On-Time Delivery Rate", f"{on_time:.1f}%")
    c2.metric("Avg Delivery Time",
              f"{delivered['delivery_days'].mean():.1f} days")
    c3.metric("Avg Review Score",
              f"{delivered['review_score'].mean():.2f} / 5")
 
    st.markdown("---")
    col1, col2 = st.columns(2)
 
    with col1:
        fig = px.histogram(
            delivered['delivery_days'].dropna(),
            nbins=40,
            title='Delivery Time Distribution',
            color_discrete_sequence=['#7F77DD'],
            labels={'value':'Days to Deliver'})
        fig.add_vline(x=delivered['delivery_days'].mean(),
                      line_dash='dash', line_color='#D85A30',
                      annotation_text=f"Mean: {delivered['delivery_days'].mean():.1f}d")
        st.plotly_chart(fig, use_container_width=True)
 
    with col2:
        review_counts = (delivered['review_score']
            .value_counts().sort_index().reset_index())
        review_counts.columns = ['Score','Count']
        fig2 = px.bar(review_counts, x='Score', y='Count',
                      title='Review Score Distribution',
                      color='Score',
                      color_continuous_scale='RdYlGn',
                      labels={'Count':'Number of Reviews'})
        st.plotly_chart(fig2, use_container_width=True)
 
    # State delivery filter
    st.markdown("---")
    st.subheader("Delivery Performance by State")
    state_del = (delivered
        .groupby('customer_state')
        .agg(avg_days=('delivery_days','mean'),
             avg_review=('review_score','mean'),
             orders=('order_id','count'))
        .round(2).reset_index()
        .sort_values('avg_days', ascending=False))
 
    min_orders = st.slider("Min orders (filter noise)",
                           50, 500, 100, 50)
    state_del  = state_del[state_del['orders'] >= min_orders]
 
    fig3 = px.scatter(state_del,
                      x='avg_days', y='avg_review',
                      size='orders', color='avg_days',
                      text='customer_state',
                      color_continuous_scale='RdYlGn_r',
                      title='Delivery Time vs Review Score by State',
                      labels={'avg_days':'Avg Delivery Days',
                              'avg_review':'Avg Review Score'})
    fig3.update_traces(textposition='top center', textfont_size=9)
    st.plotly_chart(fig3, use_container_width=True)
 