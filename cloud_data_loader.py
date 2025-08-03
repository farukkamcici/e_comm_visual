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
from pathlib import Path
import json

# Cloud deployment configuration
DEPLOYMENT_CONFIG = {
    "github_release_url": "https://github.com/farukkamcici/e_comm_visual.git/releases/download/v1.0.0/deployment_package.pkl.gz",
    "fallback_local": True,
    "cache_ttl": 3600  # Cache for 1 hour
}

@st.cache_data(ttl=DEPLOYMENT_CONFIG["cache_ttl"])
def load_deployment_package():
    """Load the pre-processed deployment package from cloud or local"""
    
    package = None
    
    # Try loading from cloud first
    try:
        st.info("🔄 Loading data from cloud...")
        response = requests.get(DEPLOYMENT_CONFIG["github_release_url"], timeout=30)
        response.raise_for_status()
        
        with gzip.open(BytesIO(response.content), 'rb') as f:
            package = pickle.load(f)
        
        st.success("✅ Cloud data loaded successfully!")
        
    except Exception as e:
        st.warning(f"⚠️ Cloud loading failed: {str(e)}")
        
        # Fallback to local file if available
        if DEPLOYMENT_CONFIG["fallback_local"]:
            try:
                st.info("🔄 Trying local deployment package...")
                with gzip.open("deployment_package.pkl.gz", 'rb') as f:
                    package = pickle.load(f)
                st.success("✅ Local deployment package loaded!")
                
            except FileNotFoundError:
                st.error("❌ No deployment package found. Please run create_deployment_package.py first.")
                return None
    
    if package:
        st.sidebar.success(f"📊 Data loaded: {package['stats']['total_sessions']:,} sessions")
        
    return package

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
    """Create cleaned data view from features for filtering"""
    session_df, user_df, brand_df, category_df = load_feature_data_cloud()
    
    if session_df is None or session_df.empty:
        return pd.DataFrame()
    
    # Create a simplified cleaned data view for filtering
    # This won't have all original events, but enough for dashboard filters
    cleaned_df = session_df[['user_id', 'user_session', 'brand', 'category_code', 'session_started_at']].copy()
    cleaned_df['event_time'] = cleaned_df['session_started_at']
    cleaned_df['event_type'] = 'session'  # Simplified for filtering
    
    return cleaned_df

def check_deployment_mode():
    """Check if running in deployment mode or local mode"""
    local_files = [
        "data/features/session_features.csv",
        "data/features/user_features.csv", 
        "outputs/summary_2025080105.json"
    ]
    
    # If any local files exist, we're in local mode
    for file_path in local_files:
        if Path(file_path).exists():
            return "local"
    
    # Check if deployment package exists
    if Path("deployment_package.pkl.gz").exists():
        return "local_deployment"
    
    return "cloud"

def get_data_loaders():
    """Get appropriate data loading functions based on deployment mode"""
    mode = check_deployment_mode()
    
    if mode == "cloud":
        st.sidebar.info("🌐 Running in cloud mode")
        return {
            "load_summary_data": load_summary_data_cloud,
            "load_feature_data": load_feature_data_cloud,
            "load_cleaned_data": load_cleaned_data_cloud
        }
    elif mode == "local_deployment":
        st.sidebar.info("📦 Running with local deployment package")
        return {
            "load_summary_data": load_summary_data_cloud,
            "load_feature_data": load_feature_data_cloud, 
            "load_cleaned_data": load_cleaned_data_cloud
        }
    else:
        st.sidebar.info("💻 Running in local development mode")
        # Import original functions
        from app import load_summary_data, load_feature_data, load_cleaned_data
        return {
            "load_summary_data": load_summary_data,
            "load_feature_data": load_feature_data,
            "load_cleaned_data": load_cleaned_data
        }