import sys
import json
import joblib
import numpy as np
from pathlib import Path

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


def model_predict(inp: dict, model, explainer, meta: dict, encoders: dict) -> dict:
    feature_cols = meta['feature_cols']
    top_langs = meta['top_languages']
    top_devops = meta['top_devops']
    ed_map = meta['ed_map']
    role_encoder = encoders['role_encoder']

    skills = [s.lower() for s in inp.get('skills', [])]
    dev_type = inp.get('devType', 'Full-Stack Developer')

    row = {}
    row['years_code_pro'] = inp.get('yearsExperience', 0)

    edu_label_map = {
        'bachelors': "Bachelor's degree",
        'masters': "Master's degree",
        'phd': 'Doctoral degree',
        'bootcamp': 'Some college',
        'self-taught': 'Something else',
    }
    ed_key = edu_label_map.get(inp.get('education', 'bachelors'), "Bachelor's degree")
    row['ed_encoded'] = ed_map.get(ed_key, 2)

    try:
        row['role_encoded'] = role_encoder.transform([dev_type])[0]
    except Exception:
        row['role_encoded'] = 0

    row['country_median_salary'] = 82000  # global median fallback

    for lang in top_langs:
        col = f'skill_{lang.replace("/","_").replace(".","_").lower()}'
        row[col] = 1 if lang.lower() in skills else 0

    for tool in top_devops:
        col = f'devops_{tool.lower()}'
        row[col] = 1 if tool.lower() in skills else 0

    row['skill_count'] = len(skills)

    X = np.array([[row.get(c, 0) for c in feature_cols]])
    predicted = float(model.predict(X)[0])
    predicted = round(predicted / 1000) * 1000

    # Confidence via estimator std
    preds = np.array([est.predict(X)[0] for est in model.estimators_])
    std = np.std(preds)
    low = round((predicted - 1.645 * std) / 1000) * 1000
    high = round((predicted + 1.645 * std) / 1000) * 1000

    # SHAP
    shap_vals = explainer.shap_values(X)[0]
    shap_dict = {col: round(float(v)) for col, v in zip(feature_cols, shap_vals)}

    # Missing high-value skills
    high_value = ['Rust', 'Go', 'Kubernetes', 'TypeScript', 'AWS', 'Terraform']
    missing = [s for s in high_value if s.lower() not in skills][:3]

    return {
        'predictedSalary': int(predicted),
        'confidenceLow': int(low),
        'confidenceHigh': int(high),
        'comparableRoles': [
            {'role': 'Senior Backend Dev', 'medianSalary': int(predicted * 1.05), 'count': 0},
            {'role': 'DevOps Engineer', 'medianSalary': int(predicted * 1.10), 'count': 0},
            {'role': 'Cloud Architect', 'medianSalary': int(predicted * 1.22), 'count': 0},
        ],
        'missingHighValueSkills': missing,
        'shapExplanation': shap_dict,
        'source': 'model',
    }


def main():
    inp = json.loads(sys.stdin.read())

    model_path = MODELS_DIR / 'salary_model.pkl'
    explainer_path = MODELS_DIR / 'shap_explainer.pkl'
    meta_path = MODELS_DIR / 'meta.json'
    encoders_path = MODELS_DIR / 'encoders.pkl'

    if not model_path.exists():
        result = formula_predict(inp)
    else:
        import json as _json
        model = joblib.load(model_path)
        explainer = joblib.load(explainer_path)
        encoders = joblib.load(encoders_path)
        with open(meta_path) as f:
            meta = _json.load(f)
        result = model_predict(inp, model, explainer, meta, encoders)

    print(json.dumps(result))


if __name__ == '__main__':
    main()
