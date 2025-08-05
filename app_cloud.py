import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import base64

# Import cloud data loader
from cloud_data_loader import get_data_loaders

def simplify_category_name(category_code):
    """Extract the last part of a dot-separated category name"""
    if pd.isna(category_code) or category_code == "":
        return category_code
    return str(category_code).split('.')[-1]

st.set_page_config(
    page_title="E-Commerce Intelligence Hub",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Get appropriate data loading functions
data_loaders = get_data_loaders()
load_summary_data = data_loaders["load_summary_data"]
load_feature_data = data_loaders["load_feature_data"] 
load_cleaned_data = data_loaders["load_cleaned_data"]

def create_sidebar_filters(session_df, cleaned_df):
    """Create sidebar filters for date range, brands, and categories"""
    st.sidebar.title("🔧 Filters & Controls")
    
    filters = {}
    
    if cleaned_df is not None and not cleaned_df.empty:
        min_date = cleaned_df['event_time'].min().date()
        max_date = cleaned_df['event_time'].max().date()
        
        st.sidebar.markdown("### 📅 Date Range")
        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        filters['date_range'] = date_range
    
    if cleaned_df is not None and not cleaned_df.empty:
        st.sidebar.markdown("### 🏷️ Brand Filter")
        all_brands = sorted(cleaned_df['brand'].dropna().unique())
        search_brand = st.sidebar.text_input("🔍 Search Brands", placeholder="Type to search...")
        
        if search_brand:
            filtered_brands = [b for b in all_brands if search_brand.lower() in b.lower()]
        else:
            filtered_brands = all_brands[:50]
            
        selected_brands = st.sidebar.multiselect(
            "Select Brands",
            options=filtered_brands,
            default=[]
        )
        filters['brands'] = selected_brands
    
    if cleaned_df is not None and not cleaned_df.empty:
        st.sidebar.markdown("### 📂 Category Filter")
        all_categories = sorted(cleaned_df['category_code'].dropna().unique())
        
        category_display_map = {simplify_category_name(cat): cat for cat in all_categories}
        display_categories = sorted(category_display_map.keys())
        
        search_category = st.sidebar.text_input("🔍 Search Categories", placeholder="Type to search...")
        
        if search_category:
            filtered_display_categories = [c for c in display_categories if search_category.lower() in c.lower()]
        else:
            filtered_display_categories = display_categories[:50]
            
        selected_display_categories = st.sidebar.multiselect(
            "Select Categories", 
            options=filtered_display_categories,
            default=[]
        )
        
        selected_categories = [category_display_map[cat] for cat in selected_display_categories]
        filters['categories'] = selected_categories
    
    return filters

def apply_filters(df, filters):
    """Apply selected filters to dataframe"""
    if df is None or df.empty:
        return df
        
    filtered_df = df.copy()
    
    if 'date_range' in filters and len(filters['date_range']) == 2:
        start_date, end_date = filters['date_range']
        if 'event_time' in df.columns:
            filtered_df = filtered_df[
                (filtered_df['event_time'].dt.date >= start_date) & 
                (filtered_df['event_time'].dt.date <= end_date)
            ]
    
    if 'brands' in filters and filters['brands']:
        if 'brand' in df.columns:
            filtered_df = filtered_df[filtered_df['brand'].isin(filters['brands'])]
    
    if 'categories' in filters and filters['categories']:
        if 'category_code' in df.columns:
            filtered_df = filtered_df[filtered_df['category_code'].isin(filters['categories'])]
    
    return filtered_df

def create_export_functions():
    """Create export functionality for reports"""
    
    def to_excel_multi_sheet(data_sheets):
        """Export multiple dataframes to different sheets in Excel"""
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            currency_format = workbook.add_format({'num_format': '$#,##0.00'})
            percent_format = workbook.add_format({'num_format': '0.00%'})
            number_format = workbook.add_format({'num_format': '#,##0'})
            
            for sheet_name, df in data_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]
                
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                for i, col in enumerate(df.columns):
                    max_len = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    ) + 2
                    worksheet.set_column(i, i, min(max_len, 50))
                
                for col_idx, col_name in enumerate(df.columns):
                    if 'revenue' in col_name.lower() or 'spending' in col_name.lower() or '$' in str(df[col_name].iloc[0] if len(df) > 0 else ''):
                        worksheet.set_column(col_idx, col_idx, None, currency_format)
                    elif 'rate' in col_name.lower() or 'conversion' in col_name.lower() or '%' in str(df[col_name].iloc[0] if len(df) > 0 else ''):
                        worksheet.set_column(col_idx, col_idx, None, percent_format)
                    elif col_name.lower() in ['count', 'sessions', 'users', 'total']:
                        worksheet.set_column(col_idx, col_idx, None, number_format)
        
        return output.getvalue()
    
    def create_comprehensive_report(summary, session_df, user_df, brand_df, category_df):
        """Create a comprehensive multi-sheet Excel report"""
        sheets = {}
        
        def remove_timezone_from_df(df):
            if df is None or df.empty:
                return df
            df_copy = df.copy()
            for col in df_copy.columns:
                if df_copy[col].dtype == 'datetime64[ns, UTC]' or str(df_copy[col].dtype).startswith('datetime64[ns'):
                    if hasattr(df_copy[col].dt, 'tz') and df_copy[col].dt.tz is not None:
                        df_copy[col] = df_copy[col].dt.tz_localize(None)
            return df_copy
        
        session_df = remove_timezone_from_df(session_df)
        user_df = remove_timezone_from_df(user_df)
        brand_df = remove_timezone_from_df(brand_df)
        category_df = remove_timezone_from_df(category_df)
        
        exec_data = []
        funnel = summary.get("funnel", {})
        revenue = summary.get("revenue", {})
        advanced = summary.get("advanced", {})
        temporal = summary.get("temporal", {})
        
        exec_data.extend([
            {"Category": "📊 Funnel Metrics", "Metric": "Total Sessions", "Value": funnel.get('total_sessions', 0), "Description": "Total number of user sessions"},
            {"Category": "📊 Funnel Metrics", "Metric": "Sessions with Views", "Value": funnel.get('sessions_with_views', 0), "Description": "Sessions that included product views"},
            {"Category": "📊 Funnel Metrics", "Metric": "Sessions with Carts", "Value": funnel.get('sessions_with_carts', 0), "Description": "Sessions where items were added to cart"},
            {"Category": "📊 Funnel Metrics", "Metric": "Sessions with Purchases", "Value": funnel.get('sessions_with_purchases', 0), "Description": "Sessions that resulted in purchases"},
            {"Category": "📊 Funnel Metrics", "Metric": "View to Cart Rate", "Value": funnel.get('view_to_cart', 0), "Description": "Conversion rate from views to cart additions"},
            {"Category": "📊 Funnel Metrics", "Metric": "View to Purchase Rate", "Value": funnel.get('view_to_purchase', 0), "Description": "Conversion rate from views to purchases"},
            
            {"Category": "💰 Revenue Metrics", "Metric": "Total Revenue", "Value": revenue.get('total_revenue', 0), "Description": "Total revenue generated"},
            {"Category": "💰 Revenue Metrics", "Metric": "Average Order Value", "Value": revenue.get('avg_order_value', 0), "Description": "Average spending per purchase"},
            {"Category": "💰 Revenue Metrics", "Metric": "Revenue Generating Sessions", "Value": revenue.get('revenue_generating_sessions', 0), "Description": "Number of sessions that generated revenue"},
            {"Category": "💰 Revenue Metrics", "Metric": "Cart Abandonment Sessions", "Value": revenue.get('cart_abandonment_sessions', 0), "Description": "Sessions with cart items but no purchase"},
            {"Category": "💰 Revenue Metrics", "Metric": "Potential Recovery Revenue", "Value": revenue.get('potential_revenue_from_abandonment', 0), "Description": "Estimated revenue from abandoned carts"},
            
            {"Category": "👥 Customer Insights", "Metric": "Loyal Users", "Value": advanced.get('loyalty', {}).get('loyal_user_count', 0), "Description": "Users with repeat purchase behavior"},
            {"Category": "👥 Customer Insights", "Metric": "Casual Users", "Value": advanced.get('loyalty', {}).get('casual_user_count', 0), "Description": "Users with infrequent purchases"},
            {"Category": "👥 Customer Insights", "Metric": "Loyal User Avg Spend", "Value": advanced.get('loyalty', {}).get('loyal_user_avg_spend', 0), "Description": "Average spending of loyal customers"},
            {"Category": "👥 Customer Insights", "Metric": "Casual User Avg Spend", "Value": advanced.get('loyalty', {}).get('casual_user_avg_spend', 0), "Description": "Average spending of casual customers"},
            
            {"Category": "⏰ Temporal Insights", "Metric": "Weekend Conversion Rate", "Value": temporal.get('weekend_conversion_rate', 0), "Description": "Conversion rate during weekends"},
            {"Category": "⏰ Temporal Insights", "Metric": "Weekday Conversion Rate", "Value": temporal.get('weekday_conversion_rate', 0), "Description": "Conversion rate during weekdays"},
            {"Category": "⏰ Temporal Insights", "Metric": "Best Conversion Hour", "Value": temporal.get('best_conversion_hour', 'N/A'), "Description": "Hour with highest conversion rate"},
            {"Category": "⏰ Temporal Insights", "Metric": "Peak Revenue Month", "Value": temporal.get('peak_revenue_month', 'N/A'), "Description": "Month with highest revenue"},
        ])
        
        sheets["📋 Executive Summary"] = pd.DataFrame(exec_data)
        
        if user_df is not None and not user_df.empty:
            user_analysis = user_df.copy()
            
            try:
                unique_values = user_analysis['user_total_spending'].nunique()
                if unique_values < 5:
                    n_segments = min(unique_values, 3)
                    labels = ['Low', 'Medium', 'High'][:n_segments]
                else:
                    n_segments = 5
                    labels = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond']
                
                user_analysis['ltv_segment'] = pd.qcut(
                    user_analysis['user_total_spending'], 
                    q=n_segments, 
                    labels=labels,
                    duplicates='drop'
                )
            except (ValueError, TypeError):
                spending_data = user_analysis['user_total_spending']
                max_spending = spending_data.max()
                
                if max_spending == 0:
                    user_analysis['ltv_segment'] = 'No Spending'
                else:
                    q33 = spending_data.quantile(0.33)
                    q67 = spending_data.quantile(0.67)
                    
                    conditions = [
                        spending_data <= q33,
                        (spending_data > q33) & (spending_data <= q67),
                        spending_data > q67
                    ]
                    choices = ['Low', 'Medium', 'High']
                    user_analysis['ltv_segment'] = pd.Series(
                        pd.Categorical.from_codes(
                            np.select(conditions, [0, 1, 2], default=0),
                            categories=choices
                        )
                    )
            
            user_analysis = user_analysis.sort_values('user_total_spending', ascending=False)
            sheets["👥 User Analysis"] = user_analysis.head(1000)
        
        if session_df is not None and not session_df.empty:
            session_analysis = session_df.copy()
            
            if 'session_duration_minutes' in session_analysis.columns:
                session_analysis['session_quality'] = pd.cut(
                    session_analysis['session_duration_minutes'], 
                    bins=[0, 1, 5, 15, float('inf')],
                    labels=['Quick', 'Short', 'Medium', 'Long']
                )
            elif 'session_duration' in session_analysis.columns:
                session_analysis['session_duration_minutes'] = session_analysis['session_duration'] / 60
                session_analysis['session_quality'] = pd.cut(
                    session_analysis['session_duration_minutes'], 
                    bins=[0, 1, 5, 15, float('inf')], 
                    labels=['Quick', 'Short', 'Medium', 'Long']
                )
            else:
                if 'n_events' in session_analysis.columns:
                    session_analysis['session_quality'] = pd.cut(
                        session_analysis['n_events'], 
                        bins=[0, 2, 5, 10, float('inf')], 
                        labels=['Quick', 'Short', 'Medium', 'Long']
                    )
                else:
                    session_analysis['session_quality'] = 'Standard'
            
            sort_column = 'session_total_spending'
            if sort_column not in session_analysis.columns:
                for col in ['total_spending', 'spending', 'revenue']:
                    if col in session_analysis.columns:
                        sort_column = col
                        break
                else:
                    numeric_cols = session_analysis.select_dtypes(include=[np.number]).columns
                    sort_column = numeric_cols[0] if len(numeric_cols) > 0 else 'user_session'
            
            session_analysis = session_analysis.sort_values(sort_column, ascending=False)
            sheets["📊 Session Analysis"] = session_analysis.head(1000)
        
        if brand_df is not None and not brand_df.empty:
            brand_performance = brand_df.copy()
            brand_performance['efficiency_score'] = brand_performance['brand_view_to_purchase_rate'] * brand_performance['purchase_spending']
            brand_performance = brand_performance.sort_values('efficiency_score', ascending=False)
            sheets["🏷️ Brand Performance"] = brand_performance
        
        if category_df is not None and not category_df.empty:
            category_performance = category_df.copy()
            category_performance['category_display'] = category_performance['category_code'].apply(simplify_category_name)
            category_performance['efficiency_score'] = category_performance['category_view_to_purchase_rate'] * category_performance['purchase_spending']
            category_performance = category_performance.sort_values('efficiency_score', ascending=False)
            sheets["📂 Category Performance"] = category_performance
        
        product_perf = summary.get("product_performance", {})
        if product_perf:
            top_brands = product_perf.get("top_brands", [])
            if top_brands:
                brands_df = pd.DataFrame(top_brands)
                brands_df['efficiency_score'] = brands_df['brand_view_to_purchase_rate'] * brands_df['purchase_spending']
                sheets["🏆 Top Brands"] = brands_df.sort_values('efficiency_score', ascending=False)
            
            top_categories = product_perf.get("top_categories", [])
            if top_categories:
                categories_df = pd.DataFrame(top_categories)
                categories_df['category_display'] = categories_df['category_code'].apply(simplify_category_name)
                categories_df['efficiency_score'] = categories_df['category_view_to_purchase_rate'] * categories_df['purchase_spending']
                sheets["📈 Top Categories"] = categories_df.sort_values('efficiency_score', ascending=False)
        
        temporal_data = []
        
        time_periods = temporal.get("time_period", [])
        if time_periods:
            for period_data in time_periods:
                temporal_data.append({
                    "Analysis_Type": "Time Period",
                    "Period": period_data.get('time_period', ''),
                    "Sessions": period_data.get('user_session', 0),
                    "Conversion_Rate": period_data.get('view_to_purchase_rate', 0),
                    "Total_Spending": period_data.get('session_total_spending', 0)
                })
        
        hourly_data = temporal.get("hourly", [])
        if hourly_data:
            for hour_data in hourly_data:
                temporal_data.append({
                    "Analysis_Type": "Hourly",
                    "Period": f"Hour {hour_data.get('hour', 0)}",
                    "Sessions": hour_data.get('user_session', 0),
                    "Conversion_Rate": hour_data.get('view_to_purchase_rate', 0),
                    "Total_Spending": hour_data.get('session_total_spending', 0)
                })
        
        quarterly_data = temporal.get("quarterly", [])
        if quarterly_data:
            for quarter_data in quarterly_data:
                temporal_data.append({
                    "Analysis_Type": "Quarterly",
                    "Period": f"Q{quarter_data.get('quarter', 0)}",
                    "Sessions": quarter_data.get('user_session', 0),
                    "Conversion_Rate": quarter_data.get('view_to_purchase_rate', 0),
                    "Total_Spending": quarter_data.get('session_total_spending', 0)
                })
        
        if temporal_data:
            sheets["⏰ Temporal Analysis"] = pd.DataFrame(temporal_data)
        
        recovery_data = []
        
        cart_abandonment = revenue.get("cart_abandonment_sessions", 0)
        potential_recovery = revenue.get("potential_revenue_from_abandonment", 0)
        recovery_data.append({
            "Opportunity_Type": "Cart Abandonment Recovery",
            "Current_State": f"{cart_abandonment:,} abandoned carts",
            "Potential_Impact": f"${potential_recovery:,.0f} potential revenue",
            "Recovery_at_25%": f"${potential_recovery * 0.25:,.0f}",
            "Recovery_at_50%": f"${potential_recovery * 0.50:,.0f}",
            "Priority": "High"
        })
        
        loyalty = advanced.get("loyalty", {})
        if loyalty:
            casual_users = loyalty.get("casual_user_count", 0)
            loyal_spend = loyalty.get("loyal_user_avg_spend", 0)
            casual_spend = loyalty.get("casual_user_avg_spend", 0)
            upgrade_potential = casual_users * (loyal_spend - casual_spend)
            
            recovery_data.append({
                "Opportunity_Type": "Casual to Loyal Upgrade",
                "Current_State": f"{casual_users:,} casual users",
                "Potential_Impact": f"${upgrade_potential:,.0f} if upgraded to loyal spending",
                "Recovery_at_25%": f"${upgrade_potential * 0.25:,.0f}",
                "Recovery_at_50%": f"${upgrade_potential * 0.50:,.0f}",
                "Priority": "Medium"
            })
        
        sheets["💡 Revenue Recovery"] = pd.DataFrame(recovery_data)
        
        insights = summary.get("insights", [])
        if insights:
            insights_data = [{"Insight_Number": i+1, "Business_Insight": insight} for i, insight in enumerate(insights)]
            sheets["🧠 Business Insights"] = pd.DataFrame(insights_data)
        
        return sheets
    
    return to_excel_multi_sheet, create_comprehensive_report

def create_customer_retention_analysis(user_df, session_df, cleaned_df):
    """Create customer retention and LTV analysis"""
    st.subheader("🔄 Customer Retention & Lifetime Value")
    
    if user_df is None or session_df is None:
        st.warning("User and session data required for retention analysis")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**👥 Customer Segmentation by Value**")
        
        user_df_copy = user_df.copy()
        
        unique_values = user_df_copy['user_total_spending'].nunique()
        if unique_values < 5:
            n_segments = min(unique_values, 3)
            labels = ['Low', 'Medium', 'High'][:n_segments]
        else:
            n_segments = 5
            labels = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond']
        
        try:
            user_df_copy['ltv_segment'] = pd.qcut(
                user_df_copy['user_total_spending'], 
                q=n_segments, 
                labels=labels,
                duplicates='drop'
            )
        except ValueError:
            spending_data = user_df_copy['user_total_spending']
            
            max_spending = spending_data.max()
            if max_spending == 0:
                user_df_copy['ltv_segment'] = 'No Spending'
            else:
                q33 = spending_data.quantile(0.33)
                q67 = spending_data.quantile(0.67)
                
                if q33 == 0 and q67 == 0:
                    bins = [0, 0.01, max_spending * 0.5, float('inf')]
                    bin_labels = ['Zero', 'Low', 'High']
                elif q33 == q67:
                    bins = [-float('inf'), q33, float('inf')]
                    bin_labels = ['Low', 'High']
                else:
                    bins = [-float('inf'), q33, q67, float('inf')]
                    bin_labels = ['Low', 'Medium', 'High']
                
                user_df_copy['ltv_segment'] = pd.cut(
                    spending_data,
                    bins=bins,
                    labels=bin_labels,
                    include_lowest=True
                )
        
        segment_stats = user_df_copy.groupby('ltv_segment').agg({
            'user_id': 'count',
            'user_total_spending': 'mean',
            'user_total_sessions': 'mean'
        }).reset_index()
        
        fig = px.bar(
            segment_stats,
            x='ltv_segment',
            y='user_total_spending',
            title="Average Spending by LTV Segment",
            color='user_total_spending',
            color_continuous_scale='Viridis'
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        high_value_users = len(user_df_copy[user_df_copy['user_total_spending'] > user_df_copy['user_total_spending'].quantile(0.8)])
        st.metric("💎 High-Value Users", f"{high_value_users:,}", help="Users in top 20% by spending")
    
    with col2:
        st.markdown("**📈 Session Frequency Distribution**")
        
        session_freq = user_df['user_total_sessions'].value_counts().head(10).sort_index()
        
        fig = px.bar(
            x=session_freq.index,
            y=session_freq.values,
            title="Distribution of Sessions per User",
            labels={'x': 'Number of Sessions', 'y': 'Number of Users'}
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        repeat_customers = len(user_df[user_df['user_total_sessions'] > 1])
        total_customers = len(user_df)
        retention_rate = (repeat_customers / total_customers) * 100 if total_customers > 0 else 0
        
        st.metric("🔄 Repeat Customer Rate", f"{retention_rate:.1f}%", help="Percentage of users with multiple sessions")
    
    with col3:
        st.markdown("**💰 Revenue Concentration Analysis**")
        
        user_df_sorted = user_df.sort_values('user_total_spending', ascending=False)
        total_revenue = user_df_sorted['user_total_spending'].sum()
        
        user_df_sorted['cumulative_users_pct'] = np.arange(1, len(user_df_sorted) + 1) / len(user_df_sorted) * 100
        user_df_sorted['cumulative_revenue_pct'] = user_df_sorted['user_total_spending'].cumsum() / total_revenue * 100
        
        fig = px.line(
            user_df_sorted.head(1000),  # Limit for performance
            x='cumulative_users_pct',
            y='cumulative_revenue_pct',
            title="Revenue Concentration (Pareto Analysis)",
            labels={'cumulative_users_pct': 'Cumulative Users (%)', 'cumulative_revenue_pct': 'Cumulative Revenue (%)'}
        )
        fig.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="80% Revenue")
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        top_20_pct_users = int(len(user_df) * 0.2)
        top_20_revenue = user_df_sorted.head(top_20_pct_users)['user_total_spending'].sum()
        revenue_concentration = (top_20_revenue / total_revenue) * 100 if total_revenue > 0 else 0
        
        st.metric("📊 80/20 Rule", f"{revenue_concentration:.0f}%", help="Revenue percentage from top 20% of users")

def create_executive_kpis(summary, filtered_df=None):
    st.markdown("### 🎯 Executive Dashboard")
    
    if filtered_df is not None and not filtered_df.empty:
        total_sessions = filtered_df['user_session'].nunique()
        sessions_with_views = filtered_df[filtered_df['event_type'] == 'view']['user_session'].nunique()
        sessions_with_carts = filtered_df[filtered_df['event_type'] == 'cart']['user_session'].nunique()
        sessions_with_purchases = filtered_df[filtered_df['event_type'] == 'purchase']['user_session'].nunique()
        
        total_revenue = filtered_df[filtered_df['event_type'] == 'purchase']['purchase_spending'].sum()
        
        view_to_cart_rate = (sessions_with_carts / sessions_with_views) * 100 if sessions_with_views > 0 else 0
        view_to_purchase_rate = (sessions_with_purchases / sessions_with_views) * 100 if sessions_with_views > 0 else 0
        
        purchase_events = filtered_df[filtered_df['event_type'] == 'purchase']
        avg_order_value = purchase_events['purchase_spending'].mean() if len(purchase_events) > 0 else 0
        
        st.info("📊 **Showing filtered metrics** - These numbers reflect your current filter selection")
    else:
        funnel = summary.get("funnel", {})
        revenue = summary.get("revenue", {})
        total_revenue = revenue.get("total_revenue", 0)
        view_to_cart_rate = funnel.get("view_to_cart", 0) * 100
        view_to_purchase_rate = funnel.get("view_to_purchase", 0) * 100
        avg_order_value = revenue.get("avg_order_value", 0)
        sessions_with_purchases = revenue.get("revenue_generating_sessions", 0)
    
    advanced = summary.get("advanced", {})
    temporal = summary.get("temporal", {})
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("💰 Total Revenue", f"${total_revenue:,.0f}", help="Total revenue generated across all completed purchases")
    
    with col2:
        st.metric("👀→🛒 View to Cart", f"{view_to_cart_rate:.1f}%", help="Percentage of product views that result in adding items to cart")
        st.metric("👀→💳 View to Purchase", f"{view_to_purchase_rate:.1f}%", help="Percentage of product views that result in completed purchases")
    
    with col3:
        st.metric("💵 Avg Order Value", f"${avg_order_value:.2f}", help="Average dollar amount spent per completed purchase")
        st.metric("🛍️ Converting Sessions", f"{sessions_with_purchases:,}", help="Number of user sessions that resulted in at least one purchase")
    
    with col4:
        loyal_premium = 0
        loyalty = advanced.get("loyalty", {})
        if loyalty:
            loyal_spend = loyalty.get("loyal_user_avg_spend", 0)
            casual_spend = loyalty.get("casual_user_avg_spend", 1)
            if casual_spend > 0:
                loyal_premium = ((loyal_spend / casual_spend - 1) * 100)
        st.metric("⭐ Loyalty Premium", f"{loyal_premium:.0f}%", help="How much more loyal users spend compared to casual users (percentage premium)")
        st.metric("👥 Loyal Users", f"{loyalty.get('loyal_user_count', 0):,}", help="Number of users classified as loyal based on repeat purchase behavior")
    
    with col5:
        weekend_conv = temporal.get("weekend_conversion_rate", 0) * 100
        weekday_conv = temporal.get("weekday_conversion_rate", 0) * 100
        st.metric("📅 Weekend Conv.", f"{weekend_conv:.1f}%", help="Conversion rate (view to purchase) during weekends (Saturday & Sunday)")
        st.metric("💼 Weekday Conv.", f"{weekday_conv:.1f}%", help="Conversion rate (view to purchase) during weekdays (Monday-Friday)")
    
    with col6:
        revenue = summary.get("revenue", {})
        cart_abandonment = revenue.get("cart_abandonment_sessions", 0)
        potential_recovery = revenue.get("potential_revenue_from_abandonment", 0)
        st.metric("🛒 Cart Abandonment", f"{cart_abandonment:,}", help="Number of sessions where users added items to cart but didn't complete purchase")
        st.metric("💡 Recovery Potential", f"${potential_recovery:,.0f}", help="Estimated revenue that could be recovered from abandoned carts if converted")

def create_insights_panel(summary):
    insights = summary.get("insights", [])
    if insights:
        st.markdown("### 🧠 Business Insights")
        
        col1, col2 = st.columns(2)
        mid_point = len(insights) // 2
        
        with col1:
            for insight in insights[:mid_point]:
                st.markdown(f"• {insight}")
        
        with col2:
            for insight in insights[mid_point:]:
                st.markdown(f"• {insight}")
    else:
        st.info("No insights available. Run the analytics pipeline to generate insights.")

def create_time_optimization_dashboard(summary, filtered_df=None):
    st.subheader("⏰ Time-of-Day Performance Optimization")
    
    if filtered_df is not None:
        st.info("📊 **Showing filtered temporal metrics** - These reflect your current filter selection")
    
    temporal = summary.get("temporal", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📊 Time Period Performance**")
        
        if filtered_df is not None and not filtered_df.empty:
            filtered_df['hour'] = filtered_df['event_time'].dt.hour
            filtered_df['time_period'] = filtered_df['hour'].apply(lambda x: 
                'Night' if x < 6 else
                'Morning' if x < 12 else  
                'Afternoon' if x < 18 else
                'Evening'
            )
            
            period_stats = []
            for period in ['Night', 'Morning', 'Afternoon', 'Evening']:
                period_data = filtered_df[filtered_df['time_period'] == period]
                if len(period_data) > 0:
                    sessions = period_data['user_session'].nunique()
                    views = period_data[period_data['event_type'] == 'view']['user_session'].nunique()
                    purchases = period_data[period_data['event_type'] == 'purchase']['user_session'].nunique()
                    conv_rate = (purchases / views) if views > 0 else 0
                    period_stats.append({
                        'time_period': period,
                        'view_to_purchase_rate': conv_rate,
                        'user_session': sessions
                    })
            
            if period_stats:
                df = pd.DataFrame(period_stats)
                df['conversion_pct'] = df['view_to_purchase_rate'] * 100
                
                fig = px.bar(
                    df,
                    x='time_period',
                    y='conversion_pct',
                    title="Conversion Rate by Time Period (Filtered)",
                    color='conversion_pct',
                    color_continuous_scale='RdYlGn',
                    labels={'conversion_pct': 'Conversion Rate (%)'}
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                best_period = df.loc[df['conversion_pct'].idxmax(), 'time_period']
                st.info(f"🎯 **Best Time**: {best_period} ({df['conversion_pct'].max():.1f}% conversion)")
        else:
            time_period_data = temporal.get("time_period", [])
            if time_period_data:
                df = pd.DataFrame(time_period_data)
                df['conversion_pct'] = df['view_to_purchase_rate'] * 100
                
                fig = px.bar(
                    df,
                    x='time_period',
                    y='conversion_pct',
                    title="Conversion Rate by Time Period",
                    color='conversion_pct',
                    color_continuous_scale='RdYlGn',
                    labels={'conversion_pct': 'Conversion Rate (%)'}
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                best_period = df.loc[df['conversion_pct'].idxmax(), 'time_period']
                st.info(f"🎯 **Best Time**: {best_period} ({df['conversion_pct'].max():.1f}% conversion)")
    
    with col2:
        st.markdown("**🕐 Hourly Conversion Pattern**")
        hourly_data = temporal.get("hourly", [])
        if hourly_data:
            df = pd.DataFrame(hourly_data)
            df['conversion_pct'] = df['view_to_purchase_rate'] * 100
            
            fig = px.line(
                df, 
                x='hour', 
                y='conversion_pct',
                title='24-Hour Conversion Trend',
                labels={'hour': 'Hour of Day', 'conversion_pct': 'Conversion Rate (%)'}
            )
            fig.update_traces(line=dict(width=3, color='#2E86AB'))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            peak_hour = temporal.get("best_conversion_hour", "N/A")
            st.success(f"🌟 **Peak Hour**: {peak_hour}:00 - Optimize ad spend here!")
    
    with col3:
        st.markdown("**📈 Weekend vs Weekday Analysis**")
        weekend_conv = temporal.get("weekend_conversion_rate", 0) * 100
        weekday_conv = temporal.get("weekday_conversion_rate", 0) * 100
        
        comparison_data = {
            'Period': ['Weekday', 'Weekend'],
            'Conversion': [weekday_conv, weekend_conv]
        }
        
        fig = px.bar(
            comparison_data,
            x='Period',
            y='Conversion',
            title="Weekend vs Weekday Performance",
            color='Conversion',
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        if weekday_conv > weekend_conv:
            diff = weekday_conv - weekend_conv
            st.warning(f"📊 Weekdays outperform weekends by {diff:.1f}pp")
        else:
            diff = weekend_conv - weekday_conv
            st.info(f"🏖️ Weekends outperform weekdays by {diff:.1f}pp")

def create_customer_value_segmentation(summary, filtered_df=None):
    st.subheader("💎 Customer Value Intelligence")
    
    revenue = summary.get("revenue", {})
    segmentation = summary.get("segmentation", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**💰 Order Value Distribution**")
        order_dist = revenue.get("order_value_distribution", {})
        if order_dist:
            labels = list(order_dist.keys())
            values = list(order_dist.values())
            
            fig = px.pie(
                values=values,
                names=labels,
                title="Customer Order Sizes",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
            
            premium_orders = order_dist.get('Premium', 0)
            total_orders = sum(values)
            if total_orders > 0:
                premium_pct = (premium_orders / total_orders) * 100
                st.metric("🏆 Premium Orders", f"{premium_pct:.1f}%", help="Percentage of orders classified as high-value premium purchases")
    
    with col2:
        st.markdown("**👥 User Spending Segments**")
        segment_stats = segmentation.get("segment_stats", [])
        if segment_stats:
            df = pd.DataFrame(segment_stats)
            non_zero_df = df[df['spending_segment'] != 'Zero Spender']
            
            fig = px.bar(
                non_zero_df,
                x='spending_segment',
                y='avg_total_spending_per_user',
                title="Average Spend by Segment",
                color='avg_conversion_rate',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=350, showlegend=False)
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        st.markdown("**🎯 Revenue Concentration**")
        segment_revenue = revenue.get("segment_revenue", {})
        if segment_revenue:
            labels = list(segment_revenue.keys())
            values = list(segment_revenue.values())
            
            fig = px.funnel(
                y=labels,
                x=values,
                title="Revenue by User Quintile"
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            
            top_20_pct = revenue.get("top_20_pct_of_user_revenue", 0) * 100
            st.error(f"⚠️ Top 20% users = {top_20_pct:.0f}% of revenue")

def create_product_portfolio_optimizer(summary, filtered_df=None):
    st.subheader("📊 Product Portfolio Intelligence")
    
    if filtered_df is not None:
        st.info("📊 **Showing filtered product metrics** - These reflect your current filter selection")
    
    product_perf = summary.get("product_performance", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🏆 Brand Performance Matrix**")
        top_brands = product_perf.get("top_brands", [])[:12]
        efficient_brands = product_perf.get("top_efficient_brands", [])
        
        if top_brands:
            df = pd.DataFrame(top_brands)
            
            df['efficiency_score'] = df['brand_view_to_purchase_rate'] * df['purchase_spending']
            
            fig = px.scatter(
                df,
                x='brand_view_to_purchase_rate',
                y='purchase_spending',
                size='efficiency_score',
                hover_name='brand',
                title="Brand Efficiency Matrix (Revenue vs Conversion)",
                labels={
                    'brand_view_to_purchase_rate': 'Conversion Rate',
                    'purchase_spending': 'Revenue ($)'
                },
                color='efficiency_score',
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            if efficient_brands:
                st.markdown("**⚡ Most Efficient Brands:**")
                for i, brand in enumerate(efficient_brands[:3], 1):
                    st.markdown(f"{i}. **{brand['brand']}** (Score: {brand['efficiency_score']:,.0f})")
    
    with col2:
        st.markdown("**📈 Category Performance Analysis**")
        top_categories = product_perf.get("top_categories", [])
        efficient_categories = product_perf.get("top_efficient_categories", [])
        
        if top_categories:
            df = pd.DataFrame(top_categories)
            df['conversion_pct'] = df['category_view_to_purchase_rate'] * 100
            df['category_display'] = df['category_code'].apply(simplify_category_name)
            
            fig = px.bar(
                df,
                x='conversion_pct',
                y='category_display',
                orientation='h',
                title="Category Conversion Rates",
                color='purchase_spending',
                color_continuous_scale='Plasma'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            avg_conversion = product_perf.get("avg_category_conversion", 0) * 100
            high_converting_count = product_perf.get("high_converting_brands_count", 0)
            
            st.metric("📊 Avg Category Conversion", f"{avg_conversion:.1f}%", help="Average conversion rate across all product categories")
            st.metric("🔥 High-Converting Brands", f"{high_converting_count}", help="Number of brands with above-average conversion rates")

def create_revenue_recovery_center(summary, filtered_df=None):
    st.subheader("💡 Revenue Recovery Opportunities")
    
    revenue = summary.get("revenue", {})
    temporal = summary.get("temporal", {})
    advanced = summary.get("advanced", {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**🛒 Cart Abandonment Recovery**")
        cart_abandonment = revenue.get("cart_abandonment_sessions", 0)
        potential_recovery = revenue.get("potential_revenue_from_abandonment", 0)
        aov = revenue.get("avg_order_value", 0)
        
        st.metric("Abandoned Carts", f"{cart_abandonment:,}", help="Sessions where users added items to cart but didn't purchase")
        st.metric("Recovery Potential", f"${potential_recovery:,.0f}", help="Estimated revenue from converting abandoned carts")
        
        recovery_rate_25 = potential_recovery * 0.25
        st.info(f"💰 25% recovery = ${recovery_rate_25:,.0f}")
    
    with col2:
        st.markdown("**⭐ Loyalty Opportunity**")
        loyalty = advanced.get("loyalty", {})
        if loyalty:
            casual_users = loyalty.get("casual_user_count", 0)
            loyal_spend = loyalty.get("loyal_user_avg_spend", 0)
            casual_spend = loyalty.get("casual_user_avg_spend", 0)
            
            st.metric("Casual Users", f"{casual_users:,}", help="Number of users with infrequent purchase behavior")
            upgrade_potential = casual_users * (loyal_spend - casual_spend)
            st.metric("Upgrade Potential", f"${upgrade_potential:,.0f}", help="Additional revenue if casual users spent like loyal users")
            
            if casual_spend > 0:
                multiplier = loyal_spend / casual_spend
                st.success(f"🚀 {multiplier:.1f}x spend uplift possible")
    
    with col3:
        st.markdown("**🎯 Multi-Brand Opportunity**")
        multi_brand_conv = advanced.get("multi_brand_conversion", 0) * 100
        single_brand_conv = advanced.get("single_brand_conversion", 0) * 100
        multi_brand_aov = advanced.get("multi_brand_aov", 0)
        single_brand_aov = advanced.get("single_brand_aov", 0)
        
        st.metric("Multi-Brand Conv.", f"{multi_brand_conv:.1f}%", help="Conversion rate for users who view multiple brands in a session")
        st.metric("Single-Brand Conv.", f"{single_brand_conv:.1f}%", help="Conversion rate for users who view only one brand in a session")
        
        if multi_brand_conv > single_brand_conv:
            diff = multi_brand_conv - single_brand_conv
            st.success(f"📈 {diff:.1f}pp higher conversion")
    
    with col4:
        st.markdown("**📅 Seasonal Optimization**")
        quarterly_data = temporal.get("quarterly", [])
        if quarterly_data:
            df = pd.DataFrame(quarterly_data)
            peak_quarter = df.loc[df['session_total_spending'].idxmax()]
            
            st.metric("Peak Quarter", f"Q{int(peak_quarter['quarter'])}", help="Quarter with highest total revenue generation")
            st.metric("Peak Revenue", f"${peak_quarter['session_total_spending']:,.0f}", help="Total revenue generated during the peak quarter")
            
            peak_month = temporal.get("peak_revenue_month", "N/A")
            st.info(f"🎯 Focus campaigns in Q{int(peak_quarter['quarter'])} & Month {peak_month}")

def create_advanced_session_analytics(summary, session_df, filtered_df=None):
    st.subheader("🔬 Advanced Session Intelligence")
    
    advanced = summary.get("advanced", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Session Quality Analysis**")
        quality_analysis = advanced.get("quality_analysis", [])
        
        if quality_analysis:
            df = pd.DataFrame(quality_analysis)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Session Count',
                x=df['session_quality'],
                y=df['user_session'],
                marker_color='lightblue'
            ))
            
            fig.add_trace(go.Scatter(
                name='Conversion Rate (%)',
                x=df['session_quality'],
                y=df['view_to_purchase_rate'] * 100,
                mode='lines+markers',
                yaxis='y2',
                line=dict(color='red', width=4)
            ))
            
            fig.update_layout(
                title='Session Quality vs Performance',
                yaxis=dict(title='Session Count'),
                yaxis2=dict(title='Conversion Rate (%)', overlaying='y', side='right'),
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
            
            high_quality = next((q for q in quality_analysis if q['session_quality'] == 'High'), None)
            if high_quality:
                st.success(f"🎯 High-quality sessions: {high_quality['view_to_purchase_rate']*100:.1f}% conversion")
    
    with col2:
        st.markdown("**🛍️ Multi-Category Shopping Behavior**")
        multi_cat_conv = advanced.get("multi_category_conversion", 0) * 100
        
        behavior_data = {
            'Shopping Behavior': ['Multi-Brand', 'Single-Brand', 'Multi-Category'],
            'Conversion Rate': [
                advanced.get("multi_brand_conversion", 0) * 100,
                advanced.get("single_brand_conversion", 0) * 100,
                multi_cat_conv
            ],
            'AOV': [
                advanced.get("multi_brand_aov", 0),
                advanced.get("single_brand_aov", 0),
                0  # Multi-category AOV not available in data
            ]
        }
        
        df = pd.DataFrame(behavior_data)
        
        fig = px.bar(
            df,
            x='Shopping Behavior',
            y='Conversion Rate',
            title="Shopping Behavior Impact",
            color='Conversion Rate',
            color_continuous_scale='Viridis'
        )
        fig.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.metric("🔄 Multi-Category Conv.", f"{multi_cat_conv:.1f}%", help="Conversion rate for users who browse multiple product categories")
        
        if session_df is not None:
            avg_brands_per_session = session_df['n_unique_brands'].mean()
            st.metric("🏷️ Avg Brands/Session", f"{avg_brands_per_session:.1f}", help="Average number of different brands viewed per user session")

def main():
    st.title("🛍️ E-Commerce Intelligence Hub")
    st.markdown("### Advanced Business Analytics Dashboard")
    st.markdown("---")
    
    summary = load_summary_data()
    session_df, user_df, brand_df, category_df = load_feature_data()
    cleaned_df = load_cleaned_data()
    
    if not summary:
        st.warning("⚠️ Summary data not available. Please run the analytics pipeline first.")
        return
    
    filters = create_sidebar_filters(session_df, cleaned_df)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Export Reports")
    to_excel, create_summary_report = create_export_functions()
    
    if st.sidebar.button("📋 Generate Comprehensive Report"):
        try:
            report_sheets = create_summary_report(summary, session_df, user_df, brand_df, category_df)
            excel_data = to_excel(report_sheets)
            st.sidebar.download_button(
                "💾 Download Excel Report",
                excel_data,
                f"ecommerce_comprehensive_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.sidebar.success("✅ Comprehensive report generated! Click download button above.")
        except Exception as e:
            st.sidebar.error(f"Error generating report: {str(e)}")
    
    filtered_cleaned_df = apply_filters(cleaned_df, filters) if cleaned_df is not None else cleaned_df
    
    if filters.get('brands') or filters.get('categories') or (filters.get('date_range') and len(filters['date_range']) == 2):
        st.info(f"🔍 **Filters Active:** {len(filters.get('brands', []))} brands, {len(filters.get('categories', []))} categories" + 
                (f", Date: {filters['date_range'][0]} to {filters['date_range'][1]}" if len(filters.get('date_range', [])) == 2 else ""))
    
    has_active_filters = filters.get('brands') or filters.get('categories') or (filters.get('date_range') and len(filters['date_range']) == 2)
    create_executive_kpis(summary, filtered_cleaned_df if has_active_filters else None)
    st.markdown("---")
    
    create_insights_panel(summary)
    st.markdown("---")
    
    create_time_optimization_dashboard(summary, filtered_cleaned_df if has_active_filters else None)
    st.markdown("---")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "💎 Customer Intelligence", 
        "📊 Product Portfolio",
        "💡 Revenue Recovery",
        "🔬 Session Analytics",
        "🔄 Retention & LTV",
        "🔍 Data Explorer"
    ])
    
    with tab1:
        create_customer_value_segmentation(summary, filtered_cleaned_df if has_active_filters else None)
    
    with tab2:
        create_product_portfolio_optimizer(summary, filtered_cleaned_df if has_active_filters else None)
    
    with tab3:
        create_revenue_recovery_center(summary, filtered_cleaned_df if has_active_filters else None)
    
    with tab4:
        create_advanced_session_analytics(summary, session_df, filtered_cleaned_df if has_active_filters else None)
    
    with tab5:
        create_customer_retention_analysis(user_df, session_df, filtered_cleaned_df)
    
    with tab6:
        st.subheader("🔍 Advanced Data Explorer")
        
        explorer_tab1, explorer_tab2, explorer_tab3, explorer_tab4 = st.tabs([
            "📊 Feature Data", 
            "📈 Summary Metrics", 
            "📋 Complete JSON",
            "🔍 Search & Filter"
        ])
        
        with explorer_tab1:
            if session_df is not None:
                st.markdown("**Session Features Sample**")
                display_df = session_df
                if filters:
                    if 'date_range' in filters and len(filters['date_range']) == 2:
                        start_date, end_date = filters['date_range']
                        display_df = session_df[
                            (session_df['session_started_at'].dt.date >= start_date) & 
                            (session_df['session_started_at'].dt.date <= end_date)
                        ]
                st.dataframe(display_df.head(100))
                
                if user_df is not None:
                    st.markdown("**Top Users by Spending**")
                    top_users = user_df.nlargest(20, 'user_total_spending')
                    st.dataframe(top_users)
        
        with explorer_tab2:
            funnel = summary.get("funnel", {})
            revenue = summary.get("revenue", {})
            
            st.markdown("**Key Performance Metrics**")
            metrics_df = pd.DataFrame([
                {"Metric": "Total Sessions", "Value": f"{funnel.get('total_sessions', 0):,}"},
                {"Metric": "Sessions with Views", "Value": f"{funnel.get('sessions_with_views', 0):,}"},
                {"Metric": "Sessions with Carts", "Value": f"{funnel.get('sessions_with_carts', 0):,}"},
                {"Metric": "Sessions with Purchases", "Value": f"{funnel.get('sessions_with_purchases', 0):,}"},
                {"Metric": "Total Revenue", "Value": f"${revenue.get('total_revenue', 0):,.2f}"},
                {"Metric": "Revenue Generating Sessions", "Value": f"{revenue.get('revenue_generating_sessions', 0):,}"},
            ])
            st.dataframe(metrics_df, use_container_width=True)
        
        with explorer_tab3:
            st.markdown("**Complete Analytics Summary**")
            st.json(summary)
        
        with explorer_tab4:
            st.markdown("**🔍 Interactive Search & Filter**")
            
            if filtered_cleaned_df is not None and not filtered_cleaned_df.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    search_term = st.text_input("🔍 Search Products/Brands/Categories", placeholder="Enter search term...")
                    
                with col2:
                    event_type_filter = st.selectbox("Filter by Event Type", 
                                                   options=['All'] + list(filtered_cleaned_df['event_type'].unique()))
                
                search_df = filtered_cleaned_df.copy()
                
                if search_term:
                    search_df = search_df[
                        search_df['brand'].str.contains(search_term, case=False, na=False) |
                        search_df['category_code'].str.contains(search_term, case=False, na=False)
                    ]
                
                if event_type_filter != 'All':
                    search_df = search_df[search_df['event_type'] == event_type_filter]
                
                st.markdown(f"**Search Results:** {len(search_df):,} records found")
                
                if len(search_df) > 0:
                    st.markdown("**📋 Sample Data:")
                    st.dataframe(search_df.head(50))
                else:
                    st.info("No results found for your search criteria.")
            else:
                st.info("No data available for search. Please check your filters.")

if __name__ == "__main__":
    main()