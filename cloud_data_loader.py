"""
Cloud data loader for Streamlit Cloud deployment
Loads pre-processed data package from GitHub Releases or other cloud storage
"""

import streamlit as st
import pandas as pd
import pickle
import gzip
import requests
from io import BytesIO

# Cloud deployment configuration
DEPLOYMENT_CONFIG = {
    "github_release_url": "https://github.com/farukkamcici/e_comm_visual/releases/download/1.0.0/deployment_package.pkl.gz",
    "fallback_local": False,  # Cloud-only deployment
    "cache_ttl": 3600  # Cache for 1 hour
}

@st.cache_data(ttl=DEPLOYMENT_CONFIG["cache_ttl"])
def load_deployment_package():
    """Load the pre-processed deployment package from cloud"""
    
    try:
        response = requests.get(DEPLOYMENT_CONFIG["github_release_url"], timeout=30)
        response.raise_for_status()
        
        with gzip.open(BytesIO(response.content), 'rb') as f:
            package = pickle.load(f)
        
        return package
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Network error loading cloud data: {str(e)}")
        st.error("Please check your internet connection and try again.")
        return None
        
    except Exception as e:
        st.error(f"❌ Error loading cloud data: {str(e)}")
        st.error("Please contact support if this issue persists.")
        return None

@st.cache_data
def load_summary_data_cloud():
    """Load summary data from deployment package"""
    package = load_deployment_package()
    if package:
        return package.get("summary", {}).get("summary", {})
    return {}

@st.cache_data  
def load_feature_data_cloud():
    """Load feature data from deployment package"""
    package = load_deployment_package()
    if not package:
        return None, None, None, None
    
    features = package.get("features", {})
    
    # Convert back to DataFrames
    session_df = pd.DataFrame(features.get("sessions", []))
    user_df = pd.DataFrame(features.get("users", []))
    brand_df = pd.DataFrame(features.get("brands", []))
    category_df = pd.DataFrame(features.get("categories", []))
    
    # Convert datetime strings back to datetime objects
    if not session_df.empty:
        session_df['session_started_at'] = pd.to_datetime(session_df['session_started_at'])
        session_df['session_ended_at'] = pd.to_datetime(session_df['session_ended_at'])
    
    return session_df, user_df, brand_df, category_df

@st.cache_data
def load_cleaned_data_cloud():
    """Load cleaned data from deployment package"""
    package = load_deployment_package()
    if not package:
        return pd.DataFrame()
    
    cleaned_data = package.get("cleaned_data", [])
    if not cleaned_data:
        return pd.DataFrame()
    
    # Convert back to DataFrame
    cleaned_df = pd.DataFrame(cleaned_data)
    
    # Convert datetime column if it exists
    if 'event_time' in cleaned_df.columns:
        cleaned_df['event_time'] = pd.to_datetime(cleaned_df['event_time'], errors='coerce')
    
    return cleaned_df

def show_data_status():
    """Show data status in sidebar (call once per app run)"""
    package = load_deployment_package()
    if package:
        metadata = package.get('metadata', {})
        total_sessions = metadata.get('total_sessions', 0)
        total_users = metadata.get('total_users', 0)
        created_at = metadata.get('created_at', 'Unknown')
        
        st.sidebar.success(f"📊 Cloud Data: {total_sessions:,} sessions, {total_users:,} users")
        st.sidebar.info(f"📅 Updated: {created_at[:10]}")

def get_data_loaders():
    """Get cloud-only data loading functions"""
    return {
        "load_summary_data": load_summary_data_cloud,
        "load_feature_data": load_feature_data_cloud,
        "load_cleaned_data": load_cleaned_data_cloud
    }