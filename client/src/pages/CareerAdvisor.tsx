import { useState } from 'react';
import { api } from '../api/client';
import { PredictionInput, PredictionOutput } from '../types';

const SKILLS = [
  'JavaScript','Python','TypeScript','Rust','Go','Java','C#','PHP','C++','Swift',
  'Kotlin','Ruby','Scala','AWS','Docker','Kubernetes','Terraform','Azure','GCP',
  'Node.js','React','PostgreSQL','Redis','GraphQL',
];

const EDU_OPTIONS: { value: PredictionInput['education']; label: string }[] = [
  { value: 'bachelors',   label: "Bachelor's Degree" },
  { value: 'masters',     label: "Master's Degree" },
  { value: 'phd',         label: 'PhD / Doctorate' },
  { value: 'bootcamp',    label: 'Bootcamp Graduate' },
  { value: 'self-taught', label: 'Self-Taught' },
];

const DEV_TYPES = [
  'Full-Stack Developer','Backend Developer','Frontend Developer',
  'DevOps Engineer','Site Reliability Engineer','Mobile Developer',
  'Data Scientist','Machine Learning Engineer','Engineering Manager',
];

export default function CareerAdvisor() {
  const [years,     setYears]     = useState(5);
  const [edu,       setEdu]       = useState<PredictionInput['education']>('bachelors');
  const [devType,   setDevType]   = useState('Full-Stack Developer');
  const [skills,    setSkills]    = useState<string[]>([]);
  const [loading,   setLoading]   = useState(false);
  const [result,    setResult]    = useState<PredictionOutput | null>(null);
  const [error,     setError]     = useState('');

  function toggleSkill(s: string) {
    setSkills(prev =>
      prev.includes(s) ? prev.filter(x => x !== s)
        : prev.length < 8 ? [...prev, s] : prev
    );
  }

  async function handlePredict() {
    setLoading(true); setError(''); setResult(null);
    try {
      const out = await api.predict({ yearsExperience: years, education: edu, devType, skills });
      setResult(out);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // Top SHAP values to display
  const topShap = result
    ? Object.entries(result.shapExplanation)
        .filter(([, v]) => v > 0)
        .sort(([,a],[,b]) => b - a)
        .slice(0, 5)
    : [];
  const maxShap = topShap[0]?.[1] ?? 1;

  return (
    <div className="container">
      <header className="page-header">
        <h1 className="page-title">Career<br />Advisor</h1>
        <p className="page-subtitle">AI-powered salary prediction · RandomForest + SHAP</p>
      </header>

      <div className="predictor-section">
        <h2 className="chart-title">Salary Predictor</h2>
        <div className="predictor-grid">

          {/* ── Inputs ── */}
          <div>
            <div className="input-group">
              <label className="input-label">Years of Professional Experience</label>
              <input type="range" min={0} max={30} value={years} step={1}
                onChange={e => setYears(Number(e.target.value))} />
              <div className="range-value">{years} year{years !== 1 ? 's' : ''}</div>
            </div>

            <div className="input-group">
              <label className="input-label">Education Level</label>
              <select value={edu} onChange={e => setEdu(e.target.value as PredictionInput['education'])}>
                {EDU_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">Developer Role</label>
              <select value={devType} onChange={e => setDevType(e.target.value)}>
                {DEV_TYPES.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">Tech Stack — select up to 8</label>
              <div className="skills-grid">
                {SKILLS.map(s => (
                  <div key={s}
                    className={`skill-tag ${skills.includes(s) ? 'selected' : ''}`}
                    onClick={() => toggleSkill(s)}
                  >{s}</div>
                ))}
              </div>
            </div>

            <button className="predict-btn" onClick={handlePredict} disabled={loading}>
              {loading ? 'Computing...' : '→ Calculate Prediction'}
            </button>
            {error && <div className="error-box" style={{ marginTop: 16 }}>⚠ {error}</div>}
          </div>

          {/* ── Result ── */}
          <div>
            {result ? (
              <div className="prediction-result">
                <div className="stat-label">Predicted Annual Salary</div>
                <div className="predicted-salary">${result.predictedSalary.toLocaleString()}</div>
                <div className="confidence-range">
                  90% band: ${(result.confidenceLow/1000).toFixed(0)}K – ${(result.confidenceHigh/1000).toFixed(0)}K
                  {result.source === 'formula' && ' · (formula mode — train model for ML)'}
                </div>

                <div className="stat-label" style={{ marginBottom: 12 }}>Key Salary Drivers (SHAP)</div>
                {topShap.map(([key, val]) => (
                  <div className="shap-bar" key={key}>
                    <div className="shap-label">{key.replace(/_/g,' ').slice(0,18)}</div>
                    <div className="shap-bar-fill" style={{ width: `${(val/maxShap)*120}px` }} />
                    <div className="shap-value">+${val.toLocaleString()}</div>
                  </div>
                ))}

                {result.missingHighValueSkills.length > 0 && (
                  <>
                    <div className="stat-label" style={{ marginTop: 24, marginBottom: 10 }}>
                      Missing High-Value Skills
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {result.missingHighValueSkills.map(s => (
                        <span key={s} style={{
                          fontFamily: 'var(--font-mono)', fontSize: 11,
                          padding: '4px 10px', border: '1px solid var(--accent-warning)',
                          color: 'var(--accent-warning)'
                        }}>{s}</span>
                      ))}
                    </div>
                  </>
                )}

                <div className="stat-label" style={{ marginTop: 24, marginBottom: 10 }}>Comparable Roles</div>
                {result.comparableRoles.map(r => (
                  <div key={r.role} style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                    → {r.role}: <span style={{ color: 'var(--accent-green)', fontFamily: 'var(--font-mono)' }}>
                      ${r.medianSalary.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                height: '100%', minHeight: 300, border: '1px dashed var(--border)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12
              }}>
                ← Fill in your profile and click predict
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
