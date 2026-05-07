import os
import sys

# Force UTF-8 on Windows so emoji in print() don't crash on cp1252 terminals.
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split, KFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
import shap

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'port':     os.getenv('DB_PORT', '5432'),
    'dbname':   os.getenv('DB_NAME', 'survey_db'),
    'user':     os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
}

def _make_engine():
    c = DB_CONFIG
    url = f"postgresql+psycopg2://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['dbname']}"
    return create_engine(url)

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

# Raw DB array columns that start with 'skill_' or 'devops_' — must be excluded
# from feature selection so lists don't leak into the numeric matrix.
RAW_ARRAY_COLS = {'devops_tools', 'languages_worked', 'languages_wanted', 'dev_type'}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    print("⏳ Connecting to PostgreSQL...")
    engine = _make_engine()
    df = pd.read_sql("""
        SELECT
            years_code_pro,
            dev_type,
            languages_worked,
            languages_wanted,
            devops_tools,
            converted_comp_yearly,
            ed_level,
            country,
            learn_code_online
        FROM responses
        WHERE converted_comp_yearly > 15000
          AND converted_comp_yearly < 400000
          AND years_code_pro IS NOT NULL
    """, engine)
    engine.dispose()

    # Cast PostgreSQL decimal/int to proper numeric types.
    df['converted_comp_yearly'] = pd.to_numeric(df['converted_comp_yearly'], errors='coerce')
    df['years_code_pro']        = pd.to_numeric(df['years_code_pro'],        errors='coerce')

    df = df.dropna(subset=['converted_comp_yearly', 'years_code_pro'])
    print(f"✅ Loaded {len(df):,} rows")
    return df


# ── Feature engineering ───────────────────────────────────────────────────────

def add_country_target_encoding(df: pd.DataFrame, target_col: str,
                                 n_splits: int = 5) -> tuple[pd.DataFrame, dict]:
    """
    K-fold target encoding for 'country' to prevent leakage.
    Returns df with new 'country_encoded' column and a mapping dict
    (computed on the full dataset) for use at inference time.
    """
    global_mean = df[target_col].mean()
    df['country_encoded'] = global_mean  # default

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    for train_idx, val_idx in kf.split(df):
        train_fold = df.iloc[train_idx]
        country_mean = train_fold.groupby('country')[target_col].mean()
        df.iloc[val_idx, df.columns.get_loc('country_encoded')] = (
            df.iloc[val_idx]['country'].map(country_mean).fillna(global_mean)
        )

    # Full-dataset mapping for inference (no leakage issue at serve time)
    country_map: dict = df.groupby('country')[target_col].mean().to_dict()
    country_map['__global_mean__'] = global_mean
    return df, country_map


def engineer_features(df: pd.DataFrame) -> tuple[pd.DataFrame, LabelEncoder, dict]:
    # ── Binary language / devops flags ──────────────────────────────────────
    # Use default-arg capture to avoid the classic Python closure bug.
    for lang in TOP_LANGUAGES:
        col = 'skill_' + lang.replace('/', '_').replace('.', '_').lower()
        df[col] = df['languages_worked'].apply(
            lambda x, _l=lang: 1 if isinstance(x, list) and _l in x else 0
        )
    for tool in TOP_DEVOPS:
        col = 'devops_' + tool.lower()
        df[col] = df['devops_tools'].apply(
            lambda x, _t=tool: 1 if isinstance(x, list) and _t in x else 0
        )

    # ── Skill count ──────────────────────────────────────────────────────────
    df['skill_count'] = df['languages_worked'].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )

    # ── Wanted-language count (future-interest signal) ───────────────────────
    df['wanted_count'] = df['languages_wanted'].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )

    # ── Education encoding ───────────────────────────────────────────────────
    # The SO 2023 CSV uses long-form labels; strip parenthetical suffixes first.
    def map_ed(val):
        if not isinstance(val, str):
            return 2
        # Try exact match
        if val in ED_MAP:
            return ED_MAP[val]
        # Try prefix match (handles "Bachelor's degree (B.A., B.S., ...)")
        for key, code in ED_MAP.items():
            if val.startswith(key):
                return code
        return 2  # default = 'Some college'

    df['ed_encoded'] = df['ed_level'].apply(map_ed)

    # ── Country target encoding (K-fold, no leakage) ─────────────────────────
    df, country_map = add_country_target_encoding(
        df, 'converted_comp_yearly', n_splits=5
    )

    # ── Primary dev-role encoding ────────────────────────────────────────────
    df['primary_role'] = df['dev_type'].apply(
        lambda x: x[0] if isinstance(x, list) and len(x) > 0 else 'Other'
    )
    le = LabelEncoder()
    df['role_encoded'] = le.fit_transform(df['primary_role'].fillna('Other'))

    # ── Boolean feature ──────────────────────────────────────────────────────
    df['learn_online'] = df['learn_code_online'].apply(
        lambda x: 1 if x is True else 0
    )

    return df, le, country_map


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    skill_cols = [
        c for c in df.columns
        if (c.startswith('skill_') or c.startswith('devops_'))
        and c not in RAW_ARRAY_COLS
    ]
    return [
        'years_code_pro', 'ed_encoded', 'role_encoded',
        'country_encoded',          # K-fold target encoding (replaces raw median)
        'skill_count', 'wanted_count',
        'learn_online',
    ] + skill_cols


# ── Training ──────────────────────────────────────────────────────────────────

def train():
    df = load_data()
    if len(df) < 100:
        print("❌ Not enough data to train. Run the import first.")
        sys.exit(1)

    df, role_encoder, country_map = engineer_features(df)
    feature_cols = get_feature_cols(df)

    X = df[feature_cols].fillna(0).astype(float)

    # ── Log-transform target ─────────────────────────────────────────────────
    # Salaries are log-normally distributed; log1p dramatically improves fit
    # because it compresses the long right tail.
    y_raw = df['converted_comp_yearly'].astype(float)
    y     = np.log1p(y_raw)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Convert to numpy — avoids pandas/XGBoost dtype compatibility issues
    X_train_np = X_train.values
    X_test_np  = X_test.values

    print(f"⏳ Training XGBoost on {len(X_train):,} samples...")
    model = XGBRegressor(
        n_estimators=1000,
        learning_rate=0.05,
        max_depth=7,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        n_jobs=-1,
        random_state=42,
        early_stopping_rounds=50,
        eval_metric='rmse',
        verbosity=0,
    )
    model.fit(
        X_train_np, y_train,
        eval_set=[(X_test_np, y_test)],
        verbose=False,
    )

    # ── Evaluate on original dollar scale ────────────────────────────────────
    y_pred_log   = model.predict(X_test_np)
    y_pred       = np.expm1(y_pred_log)
    y_test_orig  = np.expm1(y_test)

    y_train_pred_log = model.predict(X_train_np)
    y_train_pred     = np.expm1(y_train_pred_log)
    y_train_orig     = np.expm1(y_train)

    mae   = mean_absolute_error(y_test_orig, y_pred)
    rmse  = mean_squared_error(y_test_orig, y_pred) ** 0.5
    r2    = r2_score(y_test_orig, y_pred)
    r2_tr = r2_score(y_train_orig, y_train_pred)

    # Also report R² on log scale (what the model directly optimises)
    r2_log = r2_score(y_test, y_pred_log)

    print()
    print("━" * 48)
    print("  Model Evaluation")
    print("━" * 48)
    print(f"  Train R²  (accuracy)  : {r2_tr:.4f}  ({r2_tr*100:.1f}%)")
    print(f"  Test  R²  (accuracy)  : {r2:.4f}  ({r2*100:.1f}%)")
    print(f"  Test  R²  (log scale) : {r2_log:.4f}  ({r2_log*100:.1f}%)")
    print(f"  MAE                   : ${mae:,.0f}")
    print(f"  RMSE                  : ${rmse:,.0f}")
    print(f"  Best iteration        : {model.best_iteration}")
    print("━" * 48)
    print()

    # ── SHAP explainer ────────────────────────────────────────────────────────
    print("⏳ Computing SHAP explainer...")
    explainer = shap.TreeExplainer(model)

    # ── Save artefacts ────────────────────────────────────────────────────────
    model_path    = MODELS_DIR / 'salary_model.pkl'
    explainer_path = MODELS_DIR / 'shap_explainer.pkl'
    encoders_path = MODELS_DIR / 'encoders.pkl'
    meta_path     = MODELS_DIR / 'meta.json'

    joblib.dump(model,     model_path)
    joblib.dump(explainer, explainer_path)
    joblib.dump({
        'role_encoder': role_encoder,
        'country_map':  country_map,
    }, encoders_path)

    meta = {
        'feature_cols':   feature_cols,
        'top_languages':  TOP_LANGUAGES,
        'top_devops':     TOP_DEVOPS,
        'ed_map':         ED_MAP,
        'country_map':    country_map,
        'mae':            mae,
        'rmse':           rmse,
        'r2':             r2,
        'r2_train':       r2_tr,
        'r2_log':         r2_log,
        'train_rows':     len(X_train),
        'test_rows':      len(X_test),
        'log_transform':  True,   # flag so predict.py applies expm1
    }
    with open(meta_path, 'w') as f:
        json.dump({k: v for k, v in meta.items() if k != 'country_map'}, f, indent=2)

    print(f"✅ Model saved → {model_path}")
    print(f"✅ Meta  saved → {meta_path}")


if __name__ == '__main__':
    train()
