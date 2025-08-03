#!/usr/bin/env python3
"""
Create deployment package for Streamlit Cloud
Combines all processed data into a single compressed file for fast cloud loading
"""

import json
import pickle
import gzip
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_deployment_package():
    """Create a compressed deployment package with all processed data"""
    
    logger.info("🚀 Creating deployment package...")
    
    # Check if all required files exist
    required_files = {
        "session_features": "data/features/session_features.csv",
        "user_features": "data/features/user_features.csv", 
        "brand_features": "data/features/brand_features.csv",
        "category_features": "data/features/category_features.csv",
        "summary": "outputs/summary_2025080105.json"
    }
    
    for name, path in required_files.items():
        if not Path(path).exists():
            raise FileNotFoundError(f"Required file missing: {path}")
    
    # Load all feature data
    logger.info("📊 Loading feature data...")
    session_df = pd.read_csv(required_files["session_features"], 
                           parse_dates=['session_started_at', 'session_ended_at'])
    user_df = pd.read_csv(required_files["user_features"])
    brand_df = pd.read_csv(required_files["brand_features"])
    category_df = pd.read_csv(required_files["category_features"])
    
    # Load summary data
    logger.info("📈 Loading summary data...")
    with open(required_files["summary"], 'r') as f:
        summary_data = json.load(f)
    
    # Convert datetime columns to strings for JSON compatibility
    logger.info("🔄 Processing datetime columns...")
    session_df['session_started_at'] = session_df['session_started_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
    session_df['session_ended_at'] = session_df['session_ended_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Create deployment package
    logger.info("📦 Creating deployment package...")
    deployment_package = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "version": "1.0.0",
            "description": "E-commerce analytics deployment package",
            "data_source": "REES46 Marketing Platform via Kaggle"
        },
        "features": {
            "sessions": session_df.to_dict('records'),
            "users": user_df.to_dict('records'), 
            "brands": brand_df.to_dict('records'),
            "categories": category_df.to_dict('records')
        },
        "summary": summary_data,
        "stats": {
            "total_sessions": len(session_df),
            "total_users": len(user_df),
            "total_brands": len(brand_df),
            "total_categories": len(category_df),
            "data_size_mb": round((
                session_df.memory_usage(deep=True).sum() +
                user_df.memory_usage(deep=True).sum() +
                brand_df.memory_usage(deep=True).sum() +
                category_df.memory_usage(deep=True).sum()
            ) / 1024 / 1024, 2)
        }
    }
    
    # Save as compressed pickle file
    output_path = Path("deployment_package.pkl.gz")
    logger.info(f"💾 Saving to {output_path}...")
    
    with gzip.open(output_path, 'wb') as f:
        pickle.dump(deployment_package, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    # Get file size
    file_size_mb = round(output_path.stat().st_size / 1024 / 1024, 2)
    
    logger.info("✅ Deployment package created successfully!")
    logger.info(f"📊 Package stats:")
    logger.info(f"   • Sessions: {deployment_package['stats']['total_sessions']:,}")
    logger.info(f"   • Users: {deployment_package['stats']['total_users']:,}")
    logger.info(f"   • Brands: {deployment_package['stats']['total_brands']:,}")
    logger.info(f"   • Categories: {deployment_package['stats']['total_categories']:,}")
    logger.info(f"   • Memory size: {deployment_package['stats']['data_size_mb']} MB")
    logger.info(f"   • File size: {file_size_mb} MB")
    logger.info(f"   • Compression ratio: {deployment_package['stats']['data_size_mb']/file_size_mb:.1f}x")
    
    return output_path

def test_deployment_package():
    """Test loading the deployment package"""
    logger.info("🧪 Testing deployment package...")
    
    with gzip.open("deployment_package.pkl.gz", 'rb') as f:
        package = pickle.load(f)
    
    logger.info("✅ Package loads successfully!")
    logger.info(f"📊 Loaded {len(package['features']['sessions'])} sessions")
    logger.info(f"👥 Loaded {len(package['features']['users'])} users")
    
    return package

if __name__ == "__main__":
    try:
        # Create package
        output_file = create_deployment_package()
        
        # Test loading
        test_deployment_package()
        
        print("\n🎉 SUCCESS! Deployment package ready.")
        print(f"📁 File: {output_file}")
        print("📋 Next steps:")
        print("   1. Upload deployment_package.pkl.gz to GitHub Releases")
        print("   2. Modify app.py to use cloud loading")
        print("   3. Deploy to Streamlit Cloud")
        
    except Exception as e:
        logger.error(f"❌ Error creating deployment package: {e}")
        raise