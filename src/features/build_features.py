import pandas as pd
from pathlib import Path

def build_session_df(df):
    return (
        df.groupby('user_session').agg(
            user_id = ('user_id', 'first'),
            category_code = ('category_code', 'first'),
            brand = ('brand', 'first'),
            view_count = ('event_type', lambda ev: (ev == 'view').sum()),
            cart_count = ('event_type', lambda ev: (ev == 'cart').sum()),
            purchase_count = ('event_type', lambda ev: (ev == 'purchase').sum()),
            n_unique_brands = ('brand', 'nunique'),
            n_unique_categories = ('category_code', 'nunique'),
            session_started_at = ('event_time', 'min'),
            session_ended_at = ('event_time', 'max'),
            session_total_spending = ("purchase_spending", "sum"),
        ).assign(
            session_duration = lambda d: (d['session_ended_at'] - d['session_started_at']).dt.total_seconds(),
            cart_to_view_rate = lambda d: (d["cart_count"] / d["view_count"].replace(0, pd.NA)).fillna(0),
            purchase_to_cart_rate = lambda d: (d["purchase_count"] / d["cart_count"].replace(0, pd.NA)).fillna(0),
            is_weekend = lambda d: d['session_started_at'].dt.weekday >= 5
        )
        .reset_index()
    )


def build_user_df(df):
    return (
        df.groupby('user_id').agg(
            user_total_sessions = ('user_id', 'count'),
            total_view_count=('view_count', 'sum'),
            total_cart_count=('cart_count', 'sum'),
            total_purchase_count=('purchase_count', 'sum'),
            user_avg_session_duration=('session_duration', 'mean'),
            user_total_spending = ('session_total_spending', 'sum'),
        ).assign(
            user_cart_to_view_rate=lambda d: (d['total_cart_count'] / d['total_view_count'].replace(0, pd.NA)).fillna(0),
            user_purchase_to_cart_rate=lambda d: (d['total_purchase_count'] / d['total_cart_count'].replace(0, pd.NA)).fillna(0),
            user_purchase_per_session=lambda d: (d['total_purchase_count'] / d['user_total_sessions'].replace(0, pd.NA)).fillna(0),
        )
        .reset_index()
    )


def build_brand_df(df):
    br = df.groupby(['brand', 'event_type']).size().unstack(fill_value=0)
    brand_df = (
        br.assign(
            brand_cart_to_view_rate = lambda d: d['cart'] / d['view'].fillna(0),
            brand_purchase_cart_rate = lambda d: d['purchase'] / d['cart'].fillna(0),
        )
        .reset_index()
    )

    return brand_df


def build_category_df(df):
    br = df.groupby(['category_code', 'event_type']).size().unstack(fill_value=0)
    category_df = (
        br.assign(
            category_car_to_view_rate=lambda d: d['cart'] / d['view'].fillna(0),
            category_purchase_to_cart_rate=lambda d: d['purchase'] / d['cart'].fillna(0),
        )
        .reset_index()
    )

    return category_df


def run_feature_building():
    project_root = Path(__file__).parents[2]
    out_dir = project_root / "data" / "features"

    cleaned_path= project_root / "data" / "cleaned" / "cleaned_data.csv"
    cleaned_df = pd.read_csv(cleaned_path, parse_dates=['event_time'])

    session_df = build_session_df(cleaned_df)
    user_df = build_user_df(session_df)
    cat_df = build_category_df(cleaned_df)
    brand_df = build_brand_df(cleaned_df)

    session_df.to_csv(out_dir / "session_features.csv", index=False)
    user_df.to_csv(out_dir / "user_features.csv", index=False)
    cat_df.to_csv(out_dir / "category_features.csv", index=False)
    brand_df.to_csv(out_dir / "brand_features.csv", index=False)

    print(f"Feature building complete. Saved to: {out_dir}")

