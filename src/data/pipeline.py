from pathlib import Path

import pandas as pd

from clean_data import clean_data
from features.build_features import run_feature_building


def run_cleaning():
    project_root = Path(__file__).parents[2]

    cleaned_path = project_root / "data" / "cleaned" / "cleaned_data.csv"

    df_clean = clean_data()

    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(cleaned_path, index=False)
    print(f"Cleaned events saved to: {cleaned_path}")


# if __name__ == "__main__":
#
#     run_cleaning()

# if __name__ == "__main__":
#
#     run_feature_building()

if __name__ == "__main__":
    csv_set = ['brand_features', 'category_features', 'user_features', 'session_features']
    cleaned_data = Path(__file__).parents[2] / "data" / "cleaned" / "cleaned_data.csv"
    cleaned_df = pd.read_csv(cleaned_data)
    print('cleaned_data.csv:')
    print(cleaned_df.head())
    print(cleaned_df.info())
    print(cleaned_df.describe())

    for csv in csv_set:
        data_path = Path(__file__).parents[2] / "data" / "features" / f"{csv}.csv"
        df = pd.read_csv(data_path)
        print(f'{csv}.csv:')
        print(df.head())
        print(df.info())
        print(df.describe())

