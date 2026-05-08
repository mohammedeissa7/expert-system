import sys
import json
import joblib
import numpy as np
import torch
from pathlib import Path
from model_def import SalaryMLP

MODELS_DIR = Path(__file__).parent.parent / 'models'

# Fallback formula when model is not trained yet
def formula_predict(inp: dict) -> dict:
    years = inp.get('yearsExperience', 0)
    edu = inp.get('education', 'bachelors')
    dev = inp.get('devType', 'fullstack')
    skills = inp.get('skills', [])

    base = 55000 + years * 3200
    edu_mult = {'phd': 1.28, 'masters': 1.14, 'bachelors': 1.0,
                'bootcamp': 0.92, 'self-taught': 0.90}
    role_mult = {'sre': 1.20, 'devops': 1.18, 'backend': 1.08,
                 'fullstack': 1.02, 'mobile': 1.04, 'frontend': 0.97}
    base *= edu_mult.get(edu, 1.0)
    base *= role_mult.get(dev, 1.0)
    base += len(skills) * 2800

    predicted = round(base / 1000) * 1000
    low = round(predicted * 0.88 / 1000) * 1000
    high = round(predicted * 1.12 / 1000) * 1000

    high_value = ['Rust', 'Go', 'Kubernetes', 'Terraform', 'AWS', 'TypeScript']
    missing = [s for s in high_value if s.lower() not in [x.lower() for x in skills]][:3]

    return {
        'predictedSalary': predicted,
        'confidenceLow': low,
        'confidenceHigh': high,
        'comparableRoles': [
            {'role': 'Senior Backend Dev', 'medianSalary': int(predicted * 1.05), 'count': 0},
            {'role': 'DevOps Engineer', 'medianSalary': int(predicted * 1.10), 'count': 0},
            {'role': 'Cloud Architect', 'medianSalary': int(predicted * 1.22), 'count': 0},
        ],
        'missingHighValueSkills': missing,
        'shapExplanation': {
            'years_experience': round(years * 3200),
            'education': round(base * (edu_mult.get(edu, 1.0) - 1.0)),
            'skills': len(skills) * 2800,
        },
        'source': 'formula',
    }


def _load_mlp(model_path, n_features: int) -> SalaryMLP:
    """Load SalaryMLP from a .pt checkpoint (CPU-safe)."""
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=True)
    net = SalaryMLP(n_features)
    net.load_state_dict(checkpoint['model_state'])
    net.eval()
    return net


def model_predict(inp: dict, model, explainer, scaler, meta: dict, encoders: dict) -> dict:
    import torch

    feature_cols = meta['feature_cols']
    top_langs    = meta['top_languages']
    top_devops   = meta['top_devops']
    ed_map       = meta['ed_map']
    role_encoder = encoders['role_encoder']

    skills   = [s.lower() for s in inp.get('skills', [])]
    dev_type = inp.get('devType', 'Full-Stack Developer')

    row = {}
    row['years_code_pro'] = inp.get('yearsExperience', 0)

    edu_label_map = {
        'bachelors':   "Bachelor's degree",
        'masters':     "Master's degree",
        'phd':         'Doctoral degree',
        'bootcamp':    'Some college',
        'self-taught': 'Something else',
    }
    ed_key = edu_label_map.get(inp.get('education', 'bachelors'), "Bachelor's degree")
    row['ed_encoded'] = ed_map.get(ed_key, 2)

    try:
        row['role_encoded'] = int(role_encoder.transform([dev_type])[0])
    except Exception:
        row['role_encoded'] = 0

    # Country target encoding
    country_map = encoders.get('country_map', {})
    global_mean = country_map.get('__global_mean__', 82000)
    country = inp.get('country', '')
    row['country_encoded'] = country_map.get(country, global_mean)

    row['skill_count']  = len(skills)
    row['wanted_count'] = len(inp.get('wantedSkills', []))
    row['learn_online'] = 1 if inp.get('learnOnline', False) else 0

    for lang in top_langs:
        col = f'skill_{lang.replace("/","_").replace(".","_").lower()}'
        row[col] = 1 if lang.lower() in skills else 0

    for tool in top_devops:
        col = f'devops_{tool.lower()}'
        row[col] = 1 if tool.lower() in skills else 0

    # Build feature matrix and normalise
    X_raw = np.array([[row.get(c, 0) for c in feature_cols]], dtype=np.float32)
    X     = scaler.transform(X_raw).astype(np.float32)

    # Neural network inference
    with torch.no_grad():
        X_t          = torch.tensor(X)
        predicted_log = float(model(X_t).item())

    # Inverse log-transform
    if meta.get('log_transform', True):
        predicted_raw = float(np.expm1(predicted_log))
    else:
        predicted_raw = predicted_log

    predicted = round(predicted_raw / 1000) * 1000

    # Confidence interval — ±1.645σ using training RMSE as σ approximation
    rmse = meta.get('rmse', predicted * 0.25)
    low  = round(max(0, predicted - 1.645 * rmse) / 1000) * 1000
    high = round((predicted + 1.645 * rmse) / 1000) * 1000

    # SHAP (GradientExplainer returns a list; index [0] → sample, [0] → classes)
    try:
        shap_vals_raw = explainer.shap_values(torch.tensor(X))
        # GradientExplainer may return list or ndarray
        if isinstance(shap_vals_raw, list):
            shap_arr = np.array(shap_vals_raw[0]).flatten()
        else:
            shap_arr = np.array(shap_vals_raw).flatten()
        # Convert log-scale SHAP to dollar-scale (approximate)
        baseline_salary = predicted_raw
        shap_dict = {
            col: round(float(v) * baseline_salary)
            for col, v in zip(feature_cols, shap_arr)
        }
    except Exception:
        shap_dict = {}

    # Missing high-value skills
    high_value = ['Rust', 'Go', 'Kubernetes', 'TypeScript', 'AWS', 'Terraform']
    missing = [s for s in high_value if s.lower() not in skills][:3]

    return {
        'predictedSalary': int(predicted),
        'confidenceLow':   int(low),
        'confidenceHigh':  int(high),
        'comparableRoles': [
            {'role': 'Senior Backend Dev', 'medianSalary': int(predicted * 1.05), 'count': 0},
            {'role': 'DevOps Engineer',    'medianSalary': int(predicted * 1.10), 'count': 0},
            {'role': 'Cloud Architect',    'medianSalary': int(predicted * 1.22), 'count': 0},
        ],
        'missingHighValueSkills': missing,
        'shapExplanation': shap_dict,
        'source': 'model',
    }


def main():
    inp = json.loads(sys.stdin.read())

    model_path    = MODELS_DIR / 'salary_model.pt'
    scaler_path   = MODELS_DIR / 'scaler.pkl'
    explainer_path = MODELS_DIR / 'shap_explainer.pkl'
    meta_path     = MODELS_DIR / 'meta.json'
    encoders_path = MODELS_DIR / 'encoders.pkl'

    if not model_path.exists():
        result = formula_predict(inp)
    else:
        with open(meta_path) as f:
            meta = json.load(f)

        n_features = meta.get('n_features', len(meta['feature_cols']))
        model      = _load_mlp(model_path, n_features)
        scaler     = joblib.load(scaler_path)
        explainer  = joblib.load(explainer_path)
        encoders   = joblib.load(encoders_path)

        result = model_predict(inp, model, explainer, scaler, meta, encoders)

    print(json.dumps(result))


if __name__ == '__main__':
    main()
