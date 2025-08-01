import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Any

# === Thresholds / config constants ===
ALERT_DROP_PCT = 0.1  # relative change threshold for funnel alerts
LOYALTY_SESSION_CUTOFF = 5  # sessions to consider a user "loyal"
LOW_FUNNEL_ALERT_THRESHOLD = 0.1  # e.g., view→cart below 10% should be flagged

# === Duration constants ===
MAX_SESSION_DURATION_MINUTES = 120
DURATION_BINS = [-1, 1, 5, 15, 120]
DURATION_LABELS = ['<1min', '1-5min', '5-15min', '>15min']

# === Time period constants ===
TIME_PERIOD_BINS = [-1, 6, 12, 18, 24]
TIME_PERIOD_LABELS = ['Night', 'Morning', 'Afternoon', 'Evening']

# === Order value constants ===
ORDER_VALUE_BINS = [0, 25, 100, 500, float('inf')]
ORDER_VALUE_LABELS = ['Small', 'Medium', 'Large', 'Premium']

# === Activity level constants ===
ACTIVITY_LEVEL_BINS = [-1, 1, 5, 10, float('inf')]
ACTIVITY_LEVEL_LABELS = ['One-time', 'Casual', 'Regular', 'Power']

# === Spending segment labels ===
SPENDING_SEGMENT_LABELS = ['Low Nonzero', 'Mid Nonzero', 'High Nonzero', 'Top Nonzero']

# === Session quality thresholds ===
MIN_VIEWS_FOR_HIGH_QUALITY = 3
MIN_BRANDS_FOR_HIGH_QUALITY = 1

# === Revenue quintile labels ===
REVENUE_QUINTILE_LABELS = ['Bottom 20%', 'Low 20%', 'Middle 20%', 'High 20%', 'Top 20%']

# === High converting brand threshold ===
HIGH_CONVERTING_BRAND_THRESHOLD = 0.1


# === Utility ===
def _sanitize_for_json(obj: Any):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    return obj


def _validate_required_columns(df: pd.DataFrame, required_columns: list, df_name: str):
    """Validate that required columns exist in DataFrame"""
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in {df_name}: {missing_columns}")


# === Data loading ===
def load_feature_data(base_path: str = None):
    project_root = Path(base_path) if base_path else Path(__file__).parents[2]
    features_dir = project_root / "data" / "features"

    session_df = pd.read_csv(
        features_dir / "session_features.csv", parse_dates=['session_started_at', 'session_ended_at']
    )
    user_df = pd.read_csv(features_dir / "user_features.csv")
    brand_df = pd.read_csv(features_dir / "brand_features.csv")
    category_df = pd.read_csv(features_dir / "category_features.csv")

    return session_df, user_df, brand_df, category_df


# === Helper functions ===
def _analyze_loyalty(user_df: pd.DataFrame) -> dict:
    """Extract loyalty analysis to avoid duplication"""
    loyal_users = user_df[user_df['user_total_sessions'] >= LOYALTY_SESSION_CUTOFF]
    casual_users = user_df[user_df['user_total_sessions'] < LOYALTY_SESSION_CUTOFF]

    if len(loyal_users) > 0 and len(casual_users) > 0:
        return {
            'loyal_user_count': int(len(loyal_users)),
            'casual_user_count': int(len(casual_users)),
            'loyal_user_avg_spend': loyal_users['user_total_spending'].mean(),
            'casual_user_avg_spend': casual_users['user_total_spending'].mean(),
            'loyal_conversion_rate': loyal_users['user_view_to_purchase_rate'].mean(),
            'casual_conversion_rate': casual_users['user_view_to_purchase_rate'].mean()
        }
    return {}


def _assign_spending_segments(user_df: pd.DataFrame) -> pd.DataFrame:
    """Assign spending segments in a clear, readable way"""
    df = user_df.copy()
    df['spending_segment'] = 'Zero Spender'

    # Handle non-zero spenders
    is_non_zero_spender = df['user_total_spending'] > 0
    if is_non_zero_spender.sum() > 0:
        df.loc[is_non_zero_spender, 'spending_segment'] = pd.qcut(
            df.loc[is_non_zero_spender, 'user_total_spending'],
            q=4,
            labels=SPENDING_SEGMENT_LABELS,
            duplicates='drop'
        ).astype(str)

    return df


# === Analysis modules ===
def compute_conversion_funnel(session_df: pd.DataFrame) -> dict:
    # Validate required columns
    required_columns = ['view_count', 'cart_count', 'purchase_count', 'session_duration', 'view_to_purchase_rate']
    _validate_required_columns(session_df, required_columns, 'session_df')

    total_sessions = len(session_df)
    sessions_with_views = (session_df['view_count'] > 0).sum()
    sessions_with_carts = (session_df['cart_count'] > 0).sum()
    sessions_with_purchases = (session_df['purchase_count'] > 0).sum()

    view_to_cart = sessions_with_carts / sessions_with_views if sessions_with_views > 0 else 0.0
    cart_to_purchase = sessions_with_purchases / sessions_with_carts if sessions_with_carts > 0 else 0.0
    view_to_purchase = sessions_with_purchases / sessions_with_views if sessions_with_views > 0 else 0.0

    sessions = session_df.copy()
    sessions['duration_minutes'] = sessions['session_duration'] / 60
    sessions['duration_minutes_clipped'] = sessions['duration_minutes'].clip(upper=MAX_SESSION_DURATION_MINUTES)
    sessions['duration_category'] = pd.cut(
        sessions['duration_minutes_clipped'],
        bins=DURATION_BINS,
        labels=DURATION_LABELS
    )
    duration_conversion = sessions.groupby('duration_category', observed=False)['view_to_purchase_rate'].mean().fillna(
        0)

    return {
        'total_sessions': int(total_sessions),
        'sessions_with_views': int(sessions_with_views),
        'sessions_with_carts': int(sessions_with_carts),
        'sessions_with_purchases': int(sessions_with_purchases),
        'view_to_cart': view_to_cart,
        'cart_to_purchase': cart_to_purchase,
        'view_to_purchase': view_to_purchase,
        'duration_bucket_conversion': {str(k): v for k, v in duration_conversion.items()}
    }


def analyze_user_segmentation(user_df: pd.DataFrame) -> dict:
    # Validate required columns
    required_columns = ['user_id', 'user_total_spending', 'user_total_sessions', 'user_view_to_purchase_rate',
                        'user_purchase_per_session']
    _validate_required_columns(user_df, required_columns, 'user_df')

    users = _assign_spending_segments(user_df)

    # Activity level segmentation
    users['activity_level'] = pd.cut(
        users['user_total_sessions'],
        bins=ACTIVITY_LEVEL_BINS,
        labels=ACTIVITY_LEVEL_LABELS,
        include_lowest=True
    )

    # Aggregation with clearer column names
    segment_stats = users.groupby('spending_segment', observed=False).agg({
        'user_id': 'count',
        'user_total_spending': 'mean',
        'user_total_sessions': 'mean',
        'user_view_to_purchase_rate': 'mean',
        'user_purchase_per_session': 'mean'
    }).round(2).rename(columns={
        'user_id': 'user_count',
        'user_total_spending': 'avg_total_spending_per_user',
        'user_total_sessions': 'avg_total_sessions_per_user',
        'user_view_to_purchase_rate': 'avg_conversion_rate',
        'user_purchase_per_session': 'avg_purchases_per_session'
    }).reset_index()

    loyalty_summary = _analyze_loyalty(users)

    return {
        'segment_stats': segment_stats.to_dict(orient='records'),
        'loyalty': loyalty_summary
    }


def analyze_temporal(session_df: pd.DataFrame) -> dict:
    # Validate required columns
    required_columns = ['is_weekend', 'session_started_at', 'view_to_purchase_rate', 'user_session',
                        'session_total_spending']
    _validate_required_columns(session_df, required_columns, 'session_df')

    sessions = session_df.copy()
    sessions['is_weekend'] = sessions['is_weekend'].astype(bool)
    weekend_sessions = sessions[sessions['is_weekend']]
    weekday_sessions = sessions[~sessions['is_weekend']]

    weekend_conversion = weekend_sessions['view_to_purchase_rate'].mean() if len(weekend_sessions) > 0 else 0.0
    weekday_conversion = weekday_sessions['view_to_purchase_rate'].mean() if len(weekday_sessions) > 0 else 0.0

    sessions['month'] = sessions['session_started_at'].dt.month
    sessions['quarter'] = sessions['session_started_at'].dt.quarter

    monthly = sessions.groupby('month', observed=False).agg({
        'user_session': 'count',
        'session_total_spending': 'sum',
        'view_to_purchase_rate': 'mean'
    }).round(3).reset_index()

    quarterly = sessions.groupby('quarter', observed=False).agg({
        'user_session': 'count',
        'session_total_spending': 'sum',
        'view_to_purchase_rate': 'mean'
    }).round(3).reset_index()

    sessions['hour'] = sessions['session_started_at'].dt.hour
    sessions['time_period'] = pd.cut(
        sessions['hour'],
        bins=TIME_PERIOD_BINS,
        labels=TIME_PERIOD_LABELS,
        include_lowest=True
    )

    time_period = sessions.groupby('time_period', observed=False).agg({
        'user_session': 'count',
        'view_to_purchase_rate': 'mean',
        'session_total_spending': 'mean'
    }).round(3).reset_index()

    hourly = sessions.groupby('hour', observed=False).agg({
        'user_session': 'count',
        'view_to_purchase_rate': 'mean'
    }).round(3).reset_index()

    # Peak insights
    peak_activity_hour = int(hourly.loc[hourly['user_session'].idxmax(), 'hour']) if not hourly.empty else None
    best_conversion_hour = int(
        hourly.loc[hourly['view_to_purchase_rate'].idxmax(), 'hour']) if not hourly.empty else None
    peak_revenue_month = int(
        monthly.loc[monthly['session_total_spending'].idxmax(), 'month']) if not monthly.empty else None
    peak_conversion_month = int(
        monthly.loc[monthly['view_to_purchase_rate'].idxmax(), 'month']) if not monthly.empty else None

    return {
        'weekend_conversion_rate': weekend_conversion,
        'weekday_conversion_rate': weekday_conversion,
        'monthly': monthly.to_dict(orient='records'),
        'quarterly': quarterly.to_dict(orient='records'),
        'time_period': time_period.to_dict(orient='records'),
        'hourly': hourly.to_dict(orient='records'),
        'peak_activity_hour': peak_activity_hour,
        'best_conversion_hour': best_conversion_hour,
        'peak_revenue_month': peak_revenue_month,
        'peak_conversion_month': peak_conversion_month
    }


def analyze_product_performance(brand_df: pd.DataFrame, category_df: pd.DataFrame) -> dict:
    # Validate required columns
    _validate_required_columns(brand_df, ['brand', 'purchase_spending', 'brand_view_to_purchase_rate'], 'brand_df')
    _validate_required_columns(category_df, ['category_code', 'purchase_spending', 'category_view_to_purchase_rate'],
                               'category_df')

    brands = brand_df.copy()
    categories = category_df.copy()

    top_brands = brands.nlargest(10, 'purchase_spending')[['brand', 'purchase_spending', 'brand_view_to_purchase_rate']]
    avg_brand_conversion = brands['brand_view_to_purchase_rate'].mean()
    high_converting_brands_count = int((brands['brand_view_to_purchase_rate'] > HIGH_CONVERTING_BRAND_THRESHOLD).sum())
    brands['efficiency_score'] = brands['brand_view_to_purchase_rate'] * brands['purchase_spending']
    top_efficient_brands = brands.nlargest(5, 'efficiency_score')[['brand', 'efficiency_score']]

    top_categories = categories.nlargest(5, 'purchase_spending')[
        ['category_code', 'purchase_spending', 'category_view_to_purchase_rate']]
    avg_category_conversion = categories['category_view_to_purchase_rate'].mean()
    categories['efficiency_score'] = categories['category_view_to_purchase_rate'] * categories['purchase_spending']
    top_efficient_categories = categories.nlargest(3, 'efficiency_score')[['category_code', 'efficiency_score']]

    return {
        'top_brands': top_brands.to_dict(orient='records'),
        'avg_brand_conversion': avg_brand_conversion,
        'high_converting_brands_count': high_converting_brands_count,
        'top_efficient_brands': top_efficient_brands.to_dict(orient='records'),
        'top_categories': top_categories.to_dict(orient='records'),
        'avg_category_conversion': avg_category_conversion,
        'top_efficient_categories': top_efficient_categories.to_dict(orient='records'),
    }


def analyze_revenue(session_df: pd.DataFrame, user_df: pd.DataFrame) -> dict:
    # Validate required columns
    _validate_required_columns(session_df, ['session_total_spending', 'cart_count', 'purchase_count'], 'session_df')
    _validate_required_columns(user_df, ['user_total_spending'], 'user_df')

    sessions = session_df.copy()
    revenue_sessions = sessions[sessions['session_total_spending'] > 0]
    total_revenue = sessions['session_total_spending'].sum()
    revenue_generating_sessions = int((sessions['session_total_spending'] > 0).sum())
    avg_order_value = revenue_sessions['session_total_spending'].mean() if len(revenue_sessions) > 0 else 0.0

    revenue_sessions['order_value_category'] = pd.cut(
        revenue_sessions['session_total_spending'],
        bins=ORDER_VALUE_BINS,
        labels=ORDER_VALUE_LABELS
    )
    order_value_distribution = revenue_sessions['order_value_category'].value_counts().to_dict()

    # Top users analysis
    top_users = user_df.nlargest(10, 'user_total_spending')
    top_10_revenue = top_users['user_total_spending'].sum()
    total_user_revenue = user_df['user_total_spending'].sum()
    top_10_pct = (top_10_revenue / total_user_revenue) if total_user_revenue > 0 else 0.0

    # Top 20% user revenue share (by count of users, not by revenue value)
    users_by_spend = user_df.sort_values('user_total_spending', ascending=False).reset_index(drop=True)
    n_top_20_percent = max(1, int(len(users_by_spend) * 0.2))
    top_20_percent_users_revenue = users_by_spend.loc[:n_top_20_percent - 1, 'user_total_spending'].sum()
    top_20_pct_of_user_revenue = (top_20_percent_users_revenue / total_user_revenue) if total_user_revenue > 0 else 0.0

    # Revenue quintiles for breakdown
    users_for_quintiles = user_df.copy()
    users_for_quintiles['revenue_quintile'] = pd.qcut(
        users_for_quintiles['user_total_spending'].replace(0, np.nan),
        q=5,
        labels=REVENUE_QUINTILE_LABELS,
        duplicates='drop'
    )
    revenue_by_quintile = users_for_quintiles.groupby('revenue_quintile', observed=False)[
        'user_total_spending'].sum().to_dict()

    # Cart abandonment analysis
    cart_sessions = sessions[sessions['cart_count'] > 0]
    cart_abandonment_sessions = cart_sessions[cart_sessions['purchase_count'] == 0]
    potential_revenue_from_abandonment = len(cart_abandonment_sessions) * avg_order_value

    return {
        'total_revenue': total_revenue,
        'revenue_generating_sessions': revenue_generating_sessions,
        'avg_order_value': avg_order_value,
        'order_value_distribution': order_value_distribution,
        'top_10_users_revenue': top_10_revenue,
        'top_10_pct': top_10_pct,
        'top_20_pct_of_user_revenue': top_20_pct_of_user_revenue,
        'segment_revenue': revenue_by_quintile,
        'cart_abandonment_sessions': int(len(cart_abandonment_sessions)),
        'potential_revenue_from_abandonment': potential_revenue_from_abandonment
    }


def analyze_advanced(session_df: pd.DataFrame, user_df: pd.DataFrame) -> dict:
    # Validate required columns
    required_session_cols = ['n_unique_brands', 'n_unique_categories', 'view_to_purchase_rate',
                             'session_total_spending', 'session_duration', 'view_count', 'user_session']
    _validate_required_columns(session_df, required_session_cols, 'session_df')

    sessions = session_df.copy()

    # Multi-brand vs single-brand analysis
    multi_brand_sessions = sessions[sessions['n_unique_brands'] > 1]
    single_brand_sessions = sessions[sessions['n_unique_brands'] == 1]

    multi_brand_conversion = multi_brand_sessions['view_to_purchase_rate'].mean() if len(
        multi_brand_sessions) > 0 else 0.0
    single_brand_conversion = single_brand_sessions['view_to_purchase_rate'].mean() if len(
        single_brand_sessions) > 0 else 0.0

    multi_brand_revenue_sessions = multi_brand_sessions[multi_brand_sessions['session_total_spending'] > 0]
    single_brand_revenue_sessions = single_brand_sessions[single_brand_sessions['session_total_spending'] > 0]

    multi_brand_aov = multi_brand_revenue_sessions['session_total_spending'].mean() if len(
        multi_brand_revenue_sessions) > 0 else 0.0
    single_brand_aov = single_brand_revenue_sessions['session_total_spending'].mean() if len(
        single_brand_revenue_sessions) > 0 else 0.0

    # Multi-category analysis
    multi_category_sessions = sessions[sessions['n_unique_categories'] > 1]
    multi_category_conversion = multi_category_sessions['view_to_purchase_rate'].mean() if len(
        multi_category_sessions) > 0 else 0.0

    # Session quality analysis
    sessions_quality = sessions.copy()
    is_high_quality_session = (
            (sessions_quality['session_duration'] > sessions_quality['session_duration'].median()) &
            (sessions_quality['view_count'] >= MIN_VIEWS_FOR_HIGH_QUALITY) &
            (sessions_quality['n_unique_brands'] >= MIN_BRANDS_FOR_HIGH_QUALITY)
    )
    sessions_quality['session_quality'] = 'Low'
    sessions_quality.loc[is_high_quality_session, 'session_quality'] = 'High'

    quality_analysis = sessions_quality.groupby('session_quality', observed=False).agg({
        'user_session': 'count',
        'view_to_purchase_rate': 'mean',
        'session_total_spending': 'mean'
    }).round(3).reset_index().to_dict(orient='records')

    # Loyalty analysis (reusing helper function)
    loyalty_summary = _analyze_loyalty(user_df)

    return {
        'multi_brand_conversion': multi_brand_conversion,
        'single_brand_conversion': single_brand_conversion,
        'multi_brand_aov': multi_brand_aov,
        'single_brand_aov': single_brand_aov,
        'multi_category_conversion': multi_category_conversion,
        'quality_analysis': quality_analysis,
        'loyalty': loyalty_summary
    }


def generate_insights(
        session_df: pd.DataFrame,
        user_df: pd.DataFrame,
        brand_df: pd.DataFrame,
        category_df: pd.DataFrame,
        baseline: dict = None
) -> dict:
    funnel = compute_conversion_funnel(session_df)
    segmentation = analyze_user_segmentation(user_df)
    temporal = analyze_temporal(session_df)
    product_perf = analyze_product_performance(brand_df, category_df)
    revenue = analyze_revenue(session_df, user_df)
    advanced = analyze_advanced(session_df, user_df)

    insights = []

    # Basic funnel alerts & baseline comparison
    def pct_change(curr, prev):
        if prev == 0:
            return None
        return (curr - prev) / prev

    if baseline and 'summary' in baseline and 'funnel' in baseline['summary']:
        prev_funnel = baseline['summary']['funnel']
        for key in ['view_to_cart', 'cart_to_purchase', 'view_to_purchase']:
            curr_val = funnel.get(key, 0)
            prev_val = prev_funnel.get(key, 0)
            change = pct_change(curr_val, prev_val)
            if change is not None:
                if change <= -ALERT_DROP_PCT:
                    insights.append(f"⚠️ {key} dropped by {abs(change) * 100:.1f}% compared to baseline.")
                elif change >= ALERT_DROP_PCT:
                    insights.append(f"✅ {key} increased by {change * 100:.1f}% compared to baseline.")

    # Low funnel warning even without baseline
    if funnel.get('view_to_cart', 0) < LOW_FUNNEL_ALERT_THRESHOLD:
        insights.append(f"⚠️ View→Cart conversion is low ({funnel.get('view_to_cart') * 100:.1f}%).")
    if funnel.get('cart_to_purchase', 0) < LOW_FUNNEL_ALERT_THRESHOLD:
        insights.append(f"⚠️ Cart→Purchase conversion is low ({funnel.get('cart_to_purchase') * 100:.1f}%).")

    # Revenue concentration
    top_pct = revenue.get('top_10_pct', 0)
    if top_pct > 0.5:
        insights.append(f"💡 Top 10 users contribute {top_pct * 100:.1f}% of user revenue (high concentration).")
    top20_rev = revenue.get('top_20_pct_of_user_revenue', 0)
    if top20_rev > 0:
        insights.append(f"💡 Top 20% of users account for {top20_rev * 100:.1f}% of user revenue.")

    # Cart abandonment
    ca = revenue.get('cart_abandonment_sessions', 0)
    if ca > 0:
        insights.append(
            f"💰 {ca} cart abandonment sessions represent potential recovery of "
            f"${revenue.get('potential_revenue_from_abandonment', 0):,.2f}."
        )

    # Weekend vs weekday
    wc = temporal.get('weekend_conversion_rate', 0)
    wd = temporal.get('weekday_conversion_rate', 0)
    if wc > wd * 1.1:
        insights.append("📈 Weekend conversion notably higher than weekday; consider shifting spend.")
    elif wd > wc * 1.1:
        insights.append("📈 Weekday conversion notably higher than weekend; optimize campaigns accordingly.")

    # Temporal peaks
    if temporal.get('best_conversion_hour') is not None:
        insights.append(f"⏰ Best conversion hour: {temporal.get('best_conversion_hour')}:00.")
    if temporal.get('peak_revenue_month') is not None:
        insights.append(f"📅 Peak revenue month: {temporal.get('peak_revenue_month')}.")
    if temporal.get('peak_conversion_month') is not None:
        insights.append(f"📅 Peak conversion month: {temporal.get('peak_conversion_month')}.")

    # Loyalty premium
    loyalty = advanced.get('loyalty', {})
    if loyalty:
        loyal_val = loyalty.get('loyal_user_avg_spend', 0)
        casual_val = loyalty.get('casual_user_avg_spend', 1)
        if casual_val > 0:
            premium = (loyal_val / casual_val - 1) * 100
            insights.append(f"⭐ Loyal users have {premium:.1f}% higher average spend than casual users.")

    # Data quality warnings
    if revenue.get('total_revenue', 0) == 0:
        insights.append("⚠️ Total revenue is zero—check data ingestion or filtering.")
    if segmentation.get('segment_stats'):
        # flag if one segment dominates zero spenders heavily
        zero_spender = next((s for s in segmentation['segment_stats'] if s.get('spending_segment') == 'Zero Spender'),
                            None)
        if zero_spender and zero_spender.get('user_count', 0) / (
                sum(s.get('user_count', 0) for s in segmentation['segment_stats']) + 1e-9) > 0.8:
            insights.append("⚠️ Majority of users are zero spenders; consider focusing on activation strategies.")

    summary = {
        'funnel': funnel,
        'segmentation': segmentation,
        'temporal': temporal,
        'product_performance': product_perf,
        'revenue': revenue,
        'advanced': advanced,
        'insights': insights
    }

    return _sanitize_for_json(summary)


def load_summary(path: str) -> dict:
    with open(path, 'r') as f:
        return json.load(f)