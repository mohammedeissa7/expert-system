import { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, ArcElement,
  Tooltip, Legend, Title
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import { api } from '../api/client';
import { GlobalStats } from '../types';

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend, Title);

const CHART_DEFAULTS = {
  color: '#8b949e',
  borderColor: '#21262d',
  fontFamily: "'IBM Plex Mono', monospace",
};

ChartJS.defaults.color = CHART_DEFAULTS.color;
ChartJS.defaults.borderColor = CHART_DEFAULTS.borderColor;
ChartJS.defaults.font.family = CHART_DEFAULTS.fontFamily;

const ACCENTS = ['#00ff9f','#00d4ff','#ffaa00','#ff6b9d','#a78bfa','#fb923c','#34d399','#60a5fa'];

function StatCard({ label, value, change, changeDir, delay }: {
  label: string; value: string; change: string; changeDir: 'up'|'down'; delay: number;
}) {
  return (
    <div className="stat-card" style={{ animationDelay: `${delay}ms` }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className={`stat-change ${changeDir}`}>{change}</div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [langView, setLangView] = useState<'used'|'wanted'>('used');

  useEffect(() => {
    api.getStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="container">
      <div className="loading-spinner">
        <div className="spinner-ring" />
        <span>Loading analytics...</span>
      </div>
    </div>
  );

  if (error) return (
    <div className="container">
      <div className="error-box">⚠ {error}</div>
    </div>
  );

  if (!stats) return null;

  const langData = langView === 'used' ? stats.topLanguagesUsed : stats.topLanguagesWanted;

  const languagesChartData = {
    labels: langData.map(l => l.language),
    datasets: [{
      label: 'Percentage',
      data: langData.map(l => l.percentage),
      backgroundColor: '#00ff9f',
      borderWidth: 0,
    }],
  };

  const devopsChartData = {
    labels: stats.devopsTools.map(d => d.tool),
    datasets: [{
      data: stats.devopsTools.map(d => d.percentage),
      backgroundColor: ACCENTS,
      borderWidth: 0,
    }],
  };

  const salaryChartData = {
    labels: stats.salaryByRole.map(r => r.role),
    datasets: [{
      label: 'Median Salary (USD)',
      data: stats.salaryByRole.map(r => r.medianSalary),
      backgroundColor: '#00d4ff',
      borderWidth: 0,
    }],
  };

  const barOpts = (horizontal = false) => ({
    indexAxis: (horizontal ? 'y' : 'x') as 'y'|'x',
    responsive: true,
    maintainAspectRatio: !horizontal,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: '#21262d' }, ticks: { callback: (v: number|string) => horizontal ? `${v}%` : `$${Number(v)/1000}K` } },
      y: { grid: { display: !horizontal } },
    },
  });

  return (
    <div className="container">
      <header className="page-header">
        <h1 className="page-title">Stack Overflow<br />Survey Analytics 2024</h1>
        <p className="page-subtitle">90,184 Developers · 84 Questions · 314 Technologies</p>
      </header>

      <div className="stats-grid">
        <StatCard label="Total Respondents" value={`${(stats.totalRespondents/1000).toFixed(0)}K`} change="↑ 12% vs 2023" changeDir="up" delay={0} />
        <StatCard label="Avg Salary (Global)" value={`$${(stats.avgSalaryGlobal/1000).toFixed(0)}K`} change="↑ 10% YoY" changeDir="up" delay={100} />
        <StatCard label="AI Tool Adoption" value={`${stats.aiToolAdoption}%`} change="↑ 35% vs 2023" changeDir="up" delay={200} />
        <StatCard label="Online Learners" value={`${stats.onlineLearners}%`} change="↑ 10% vs 2023" changeDir="up" delay={300} />
      </div>

      <div className="dashboard-grid">
      
        {/* Salary by Role */}
        <div className="chart-card full-width" style={{ animationDelay: '300ms', height: 380 }}>
          <div className="chart-header">
            <h2 className="chart-title">Median Salary by Developer Role</h2>
          </div>
          <div style={{ height: 300 }}>
            <Bar data={salaryChartData} options={{
              ...barOpts(false),
              maintainAspectRatio: false,
              scales: {
                y: { grid: { color: '#21262d' }, ticks: { callback: (v: number|string) => `$${Number(v)/1000}K` } },
                x: { grid: { display: false } },
              },
            } as any} />
          </div>
        </div>
      </div>
    </div>
  );
}
