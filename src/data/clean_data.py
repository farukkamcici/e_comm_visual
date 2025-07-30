import pandas as pd

def clean_data():

    data_path = "../../data/raw/events.csv"

    df = pd.read_csv(data_path)
    # pd.set_option('display.max_columns', None)

    #cleaning
    df = df.drop_duplicates()
    df = df.dropna(subset=['user_session'])
    df['brand'] = df['brand'].fillna('unknown')
    df['event_time'] = pd.to_datetime(df['event_time'], errors='coerce')
    df['hour'] = df['event_time'].dt.hour
    df['weekday'] = df['event_time'].dt.weekday
    df['month'] = df['event_time'].dt.month

    bins = [0,6,12,18,24]
    labels=['night','morning','afternoon','evening']
    df['event_period'] = pd.cut(df['hour'], bins=bins, labels=labels,  right=False)

    df['session_start'] = df.groupby('user_session')['event_time'].transform('min')
    df['time_since_start'] = (df['event_time'] - df['session_start']).dt.total_seconds()
    df['prev_event_gap'] = df.groupby('user_session')['event_time'].diff().dt.total_seconds().fillna(0)

    return df


