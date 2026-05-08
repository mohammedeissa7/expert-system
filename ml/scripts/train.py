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
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import shap
from model_def import SalaryMLP

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

    X = df[feature_cols].fillna(0).astype(float).values

    # ── Log-transform target ─────────────────────────────────────────────────
    # Salaries are log-normally distributed; log1p dramatically improves fit
    # because it compresses the long right tail.
    y_raw = df['converted_comp_yearly'].astype(float).values
    y     = np.log1p(y_raw)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # ── Feature normalisation ────────────────────────────────────────────────
    # Neural networks are sensitive to feature scale; StandardScaler is
    # fitted only on training data to prevent leakage.
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test  = scaler.transform(X_test)

    # ── PyTorch tensors ──────────────────────────────────────────────────────
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"⚡ Using device: {device}")

    def to_tensor(arr, dtype=torch.float32):
        return torch.tensor(arr, dtype=dtype).to(device)

    X_train_t = to_tensor(X_train)
    y_train_t = to_tensor(y_train)
    X_test_t  = to_tensor(X_test)
    y_test_t  = to_tensor(y_test)

    train_ds = TensorDataset(X_train_t, y_train_t)
    train_dl = DataLoader(train_ds, batch_size=256, shuffle=True)

    # ── Model, optimiser, scheduler ──────────────────────────────────────────
    n_features = X_train.shape[1]
    model = SalaryMLP(n_features).to(device)

    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimiser, mode='min', factor=0.5, patience=10, min_lr=1e-6
    )
    criterion = nn.HuberLoss(delta=0.5)   # robust to salary outliers

    # ── Training loop with early stopping ────────────────────────────────────
    print(f"⏳ Training Neural Network on {len(X_train):,} samples...")
    EPOCHS         = 300
    PATIENCE       = 30
    best_val_loss  = float('inf')
    no_improve     = 0
    best_state     = None

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            optimiser.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimiser.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(X_train)

        model.eval()
        with torch.no_grad():
            val_pred = model(X_test_t)
            val_loss = criterion(val_pred, y_test_t).item()

        scheduler.step(val_loss)

        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            no_improve    = 0
            best_state    = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            no_improve += 1

        if epoch % 25 == 0 or epoch == 1:
            lr = optimiser.param_groups[0]['lr']
            print(f"  Epoch {epoch:>3}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  lr={lr:.6f}")

        if no_improve >= PATIENCE:
            print(f"  ⏹  Early stopping at epoch {epoch} (no improvement for {PATIENCE} epochs)")
            break

    # Restore best weights
    model.load_state_dict(best_state)
    model.eval()

    # ── Evaluate on original dollar scale ────────────────────────────────────
    with torch.no_grad():
        y_pred_log  = model(X_test_t).cpu().numpy()
        y_train_pred_log = model(X_train_t).cpu().numpy()

    y_pred      = np.expm1(y_pred_log)
    y_test_orig = np.expm1(y_test)
    y_train_pred     = np.expm1(y_train_pred_log)
    y_train_orig     = np.expm1(y_train)

    mae   = mean_absolute_error(y_test_orig, y_pred)
    rmse  = mean_squared_error(y_test_orig, y_pred) ** 0.5
    r2    = r2_score(y_test_orig, y_pred)
    r2_tr = r2_score(y_train_orig, y_train_pred)
    r2_log = r2_score(y_test, y_pred_log)

    print()
    print("━" * 48)
    print("  Model Evaluation  (Neural Network MLP)")
    print("━" * 48)
    print(f"  Train R²  (accuracy)  : {r2_tr:.4f}  ({r2_tr*100:.1f}%)")
    print(f"  Test  R²  (accuracy)  : {r2:.4f}  ({r2*100:.1f}%)")
    print(f"  Test  R²  (log scale) : {r2_log:.4f}  ({r2_log*100:.1f}%)")
    print(f"  MAE                   : ${mae:,.0f}")
    print(f"  RMSE                  : ${rmse:,.0f}")
    print("━" * 48)
    print()

    # ── SHAP GradientExplainer ────────────────────────────────────────────────
    # Use a small background sample (200 rows) for efficiency.
    print("⏳ Computing SHAP explainer...")
    background = X_train_t[:200]
    explainer = shap.GradientExplainer(model, background)

    # ── Save artefacts ────────────────────────────────────────────────────────
    model_path     = MODELS_DIR / 'salary_model.pt'
    scaler_path    = MODELS_DIR / 'scaler.pkl'
    explainer_path = MODELS_DIR / 'shap_explainer.pkl'
    encoders_path  = MODELS_DIR / 'encoders.pkl'
    meta_path      = MODELS_DIR / 'meta.json'

    # Move model to CPU before saving so it loads cleanly on CPU-only machines
    model.cpu()
    torch.save({'model_state': model.state_dict(), 'n_features': n_features}, model_path)
    joblib.dump(scaler,    scaler_path)
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
        'log_transform':  True,    # flag so predict.py applies expm1
        'model_type':     'mlp',   # discriminator for predict.py
        'n_features':     n_features,
    }
    with open(meta_path, 'w') as f:
        json.dump({k: v for k, v in meta.items() if k != 'country_map'}, f, indent=2)

    print(f"✅ Model saved  → {model_path}")
    print(f"✅ Scaler saved → {scaler_path}")
    print(f"✅ Meta  saved  → {meta_path}")


if __name__ == '__main__':
    train()
