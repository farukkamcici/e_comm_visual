"""
Cloud data loader for Streamlit Cloud deployment
Loads pre-processed data package from GitHub Releases or other cloud storage
"""

import streamlit as st
import pandas as pd
import requests
from pathlib import Path
import json

# Cloud deployment configuration - Now using JSON only
DEPLOYMENT_CONFIG = {
    "github_release_url": "https://github.com/farukkamcici/e_comm_visual/releases/download/1.0.0/summary_2025080105.json",
    "fallback_local": True,
    "cache_ttl": 3600  # Cache for 1 hour
}

@st.cache_data(ttl=DEPLOYMENT_CONFIG["cache_ttl"])
def load_deployment_package():
    """Load the JSON summary deployment package from cloud or local"""
    
    package = None
    
    # Try loading from cloud first
    try:
        response = requests.get(DEPLOYMENT_CONFIG["github_release_url"], timeout=30)
        response.raise_for_status()
        
        # Load as JSON directly instead of pickle
        package = response.json()
        
    except Exception as e:
        st.warning(f"⚠️ Cloud loading failed: {str(e)}")
        
        # Fallback to local file if available
        if DEPLOYMENT_CONFIG["fallback_local"]:
            try:
                with open("outputs/summary_2025080105.json", 'r') as f:
                    package = json.load(f)
                
            except FileNotFoundError:
                st.error("❌ No JSON summary found. Please run the analytics pipeline first.")
                return None
    
    if package and 'summary' in package:
        funnel = package.get('summary', {}).get('funnel', {})
        total_sessions = funnel.get('total_sessions', 0)
        st.sidebar.success(f"📊 JSON Summary loaded: {total_sessions:,} sessions")
        
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
    """Feature data not available in cloud mode - JSON summary only"""
    return None, None, None, None

@st.cache_data
def load_cleaned_data_cloud():
    """Raw data not available in cloud mode - JSON summary only"""
    return pd.DataFrame()

def check_deployment_mode():
    """Check if running in deployment mode or local mode"""
    # Check if local JSON summary exists
    if Path("outputs/summary_2025080105.json").exists():
        return "local"
    
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
    else:
        st.sidebar.info("💻 Running in local development mode")
        # Import original functions
        from app import load_summary_data, load_feature_data, load_cleaned_data
        return {
            "load_summary_data": load_summary_data,
            "load_feature_data": load_feature_data,
            "load_cleaned_data": load_cleaned_data
        }