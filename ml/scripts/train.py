import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
import psycopg2
import shap
from pathlib import Path
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / 'server' / '.env')

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'port':     os.getenv('DB_PORT', '5432'),
    'dbname':   os.getenv('DB_NAME', 'survey_db'),
    'user':     os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
}

MODELS_DIR = Path(__file__).parent.parent / 'models'
MODELS_DIR.mkdir(exist_ok=True)

TOP_LANGUAGES = [
    'JavaScript', 'Python', 'TypeScript', 'Java', 'C#', 'PHP', 'C++', 'Go',
    'Rust', 'Kotlin', 'Ruby', 'Swift', 'Dart', 'Scala', 'R',
    'HTML/CSS', 'SQL', 'Bash/Shell', 'PowerShell', 'Node.js',
]

TOP_DEVOPS = ['AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Heroku', 'DigitalOcean', 'Firebase']

ED_MAP = {
    "Bachelor's degree": 0,
    "Master's degree": 1,
    "Professional degree": 1,
    "Some college": 2,
    "Associate degree": 2,
    "Secondary school": 3,
    "Primary/elementary school": 4,
    "Doctoral degree": 5,
    "Something else": 2,
}


def load_data():
    print("⏳ Connecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql("""
        SELECT
            years_code_pro,
            dev_type,
            languages_worked,
            devops_tools,
            converted_comp_yearly,
            ed_level,
            country
        FROM responses
        WHERE converted_comp_yearly > 10000
          AND converted_comp_yearly < 500000
          AND years_code_pro IS NOT NULL
    """, conn)
    conn.close()
    print(f"✅ Loaded {len(df):,} rows")
    return df


def engineer_features(df: pd.DataFrame):
    # Binary skill features
    for lang in TOP_LANGUAGES:
        col = f'skill_{lang.replace("/", "_").replace(".", "_").lower()}'
        df[col] = df['languages_worked'].apply(
            lambda x: 1 if x and lang in x else 0
        )
    for tool in TOP_DEVOPS:
        col = f'devops_{tool.lower()}'
        df[col] = df['devops_tools'].apply(
            lambda x: 1 if x and tool in x else 0
        )

    # Skill count
    df['skill_count'] = df['languages_worked'].apply(
        lambda x: len(x) if x else 0
    )

    # Education encoding
    df['ed_encoded'] = df['ed_level'].map(ED_MAP).fillna(2)

    # Country median salary (as feature)
    country_salary = df.groupby('country')['converted_comp_yearly'].median()
    df['country_median_salary'] = df['country'].map(country_salary).fillna(
        df['converted_comp_yearly'].median()
    )

    # Primary role encoding
    df['primary_role'] = df['dev_type'].apply(
        lambda x: x[0] if x and len(x) > 0 else 'Other'
    )
    le = LabelEncoder()
    df['role_encoded'] = le.fit_transform(df['primary_role'].fillna('Other'))

    return df, le


def get_feature_cols(df: pd.DataFrame):
    skill_cols = [c for c in df.columns if c.startswith('skill_') or c.startswith('devops_')]
    return ['years_code_pro', 'ed_encoded', 'role_encoded', 'country_median_salary'] + skill_cols


def train():
    df = load_data()
    if len(df) < 100:
        print("❌ Not enough data to train. Run the import first.")
        sys.exit(1)

    df, role_encoder = engineer_features(df)
    feature_cols = get_feature_cols(df)

    X = df[feature_cols].fillna(0)
    y = df['converted_comp_yearly']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"⏳ Training RandomForestRegressor on {len(X_train):,} samples...")
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=20,
        min_samples_split=5,
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"✅ MAE = ${mae:,.0f}")

    # SHAP explainer (TreeExplainer is fast for RF)
    print("⏳ Computing SHAP explainer...")
    explainer = shap.TreeExplainer(model)

    # Save artifacts
    model_path = MODELS_DIR / 'salary_model.pkl'
    explainer_path = MODELS_DIR / 'shap_explainer.pkl'
    meta_path = MODELS_DIR / 'meta.json'

    joblib.dump(model, model_path)
    joblib.dump(explainer, explainer_path)

    meta = {
        'feature_cols': feature_cols,
        'top_languages': TOP_LANGUAGES,
        'top_devops': TOP_DEVOPS,
        'ed_map': ED_MAP,
        'mae': mae,
        'train_rows': len(X_train),
    }
    joblib.dump({**meta, 'role_encoder': role_encoder}, MODELS_DIR / 'encoders.pkl')
    with open(meta_path, 'w') as f:
        json.dump({k: v for k, v in meta.items() if k != 'role_encoder'}, f, indent=2)

    print(f"✅ Model saved → {model_path}")
    print(f"✅ Meta  saved → {meta_path}")
    print(f"   MAE: ${mae:,.0f}")


if __name__ == '__main__':
    train()
