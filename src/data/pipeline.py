from pathlib import Path
from clean_data import clean_data

def run_pipeline():
    project_root = Path(__file__).parents[2]

    cleaned_path = project_root / "data" / "cleaned" / "cleaned_data.csv"

    df_clean = clean_data()

    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(cleaned_path, index=False)
    print(f"Cleaned events saved to: {cleaned_path}")

if __name__ == "__main__":
    run_pipeline()
