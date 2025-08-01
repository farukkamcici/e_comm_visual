import pandas as pd
from pathlib import Path


def build_session_df(df):
    # First, let's get unique product counts per session and event type
    unique_products = (
        df.groupby(['user_session', 'event_type'])['product_id']
        .nunique()
        .unstack(fill_value=0)
        .add_suffix('_unique')
    )

    # Main session aggregation
    session_df = (
        df.groupby('user_session').agg(
            user_id=('user_id', 'first'),
            category_code=('category_code', 'first'),
            brand=('brand', 'first'),
            view_count=('event_type', lambda ev: (ev == 'view').sum()),
            cart_count=('event_type', lambda ev: (ev == 'cart').sum()),
            purchase_count=('event_type', lambda ev: (ev == 'purchase').sum()),
            n_unique_brands=('brand', 'nunique'),
            n_unique_categories=('category_code', 'nunique'),
            session_started_at=('event_time', 'min'),
            session_ended_at=('event_time', 'max'),
            session_total_spending=("purchase_spending", "sum"),
        )
        .reset_index()
    )

    # Merge with unique product counts
    session_df = session_df.merge(
        unique_products.reset_index(),
        on='user_session',
        how='left'
    ).fillna(0)

    # Add computed columns
    return session_df.assign(
        session_duration=lambda d: (d['session_ended_at'] - d['session_started_at']).dt.total_seconds(),
        view_to_purchase_rate=lambda d: (d["purchase_unique"] / d["view_unique"].replace(0, pd.NA)).fillna(0),
        is_weekend=lambda d: d['session_started_at'].dt.weekday >= 5
    )


def build_user_df(df):
    return (
        df.groupby('user_id').agg(
            user_total_sessions=('user_session', 'nunique'),
            total_view_count=('view_count', 'sum'),
            total_cart_count=('cart_count', 'sum'),
            total_purchase_count=('purchase_count', 'sum'),
            total_unique_purchase_count=('purchase_unique', 'sum'),
            total_unique_view_count=('view_unique', 'sum'),
            user_avg_session_duration=('session_duration', 'mean'),
            user_total_spending=('session_total_spending', 'sum'),
        ).assign(
            user_view_to_purchase_rate=lambda d: (
                d['total_unique_purchase_count'] / d['total_unique_view_count'].replace(0, pd.NA)
            ).fillna(0).clip(upper=1.0),
            user_purchase_per_session=lambda d: (
                d['total_purchase_count'] / d['user_total_sessions'].replace(0, pd.NA)
            ).fillna(0),
        )
        .reset_index()
    )


def build_brand_df(df):
    # Get unique product counts by brand and event type
    unique_brand_products = (
        df.groupby(['brand', 'event_type'])['product_id']
        .nunique()
        .unstack(fill_value=0)
    )

    brand_spending = (
        df[df['event_type'] == 'purchase']
        .groupby('brand')['purchase_spending']
        .sum()
        .reset_index()
    )

    brand_df = (
        unique_brand_products.assign(
            brand_view_to_purchase_rate=lambda d: (d['purchase'] / d['view'].replace(0, pd.NA)).fillna(0),
        )
        .reset_index()
        .merge(brand_spending, on='brand', how='left')
        .fillna({'purchase_spending': 0})
    )

    return brand_df


def build_category_df(df):
    # Get unique product counts by category and event type
    unique_category_products = (
        df.groupby(['category_code', 'event_type'])['product_id']
        .nunique()
        .unstack(fill_value=0)
    )

    category_spending = (
        df[df['event_type'] == 'purchase']
        .groupby('category_code')['purchase_spending']
        .sum()
        .reset_index()
    )

    category_df = (
        unique_category_products.assign(
            category_view_to_purchase_rate=lambda d: (d['purchase'] / d['view'].replace(0, pd.NA)).fillna(0),
        )
        .reset_index()
        .merge(category_spending, on='category_code', how='left')
        .fillna({'purchase_spending': 0})
    )

    return category_df


def run_feature_building():
    project_root = Path(__file__).parents[2]
    out_dir = project_root / "data" / "features"

    cleaned_path = project_root / "data" / "cleaned" / "cleaned_data.csv"
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


if __name__ == "__main__":
    run_feature_building()