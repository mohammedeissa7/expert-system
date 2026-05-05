import { AppDataSource } from '../config/database';
import { GlobalStats, LanguageStat, RoleSalary, DevOpsStat } from '../../../shared/types';

// Fallback mock data when DB is empty
const MOCK_STATS: GlobalStats = {
  totalRespondents: 90184,
  avgSalaryGlobal: 82000,
  aiToolAdoption: 77,
  onlineLearners: 80,
  topLanguagesUsed: [
    { language: 'JavaScript', percentage: 63.61 },
    { language: 'Python', percentage: 49.28 },
    { language: 'TypeScript', percentage: 38.87 },
    { language: 'Java', percentage: 30.49 },
    { language: 'C#', percentage: 27.62 },
    { language: 'PHP', percentage: 20.87 },
    { language: 'C++', percentage: 20.43 },
    { language: 'Go', percentage: 13.24 },
  ],
  topLanguagesWanted: [
    { language: 'Rust', percentage: 30.52 },
    { language: 'Python', percentage: 27.89 },
    { language: 'Go', percentage: 25.10 },
    { language: 'TypeScript', percentage: 22.33 },
    { language: 'Kotlin', percentage: 18.71 },
    { language: 'JavaScript', percentage: 17.44 },
    { language: 'Swift', percentage: 14.61 },
    { language: 'C++', percentage: 12.90 },
  ],
  salaryByRole: [
    { role: 'Senior Exec / VP', medianSalary: 124000, count: 1200 },
    { role: 'Engineering Manager', medianSalary: 119000, count: 2100 },
    { role: 'Site Reliability Engineer', medianSalary: 115000, count: 3400 },
    { role: 'DevOps', medianSalary: 115000, count: 5600 },
    { role: 'Backend Developer', medianSalary: 89000, count: 12000 },
    { role: 'Full-Stack Developer', medianSalary: 82000, count: 18000 },
    { role: 'Mobile Developer', medianSalary: 85000, count: 6200 },
    { role: 'Frontend Developer', medianSalary: 78000, count: 9800 },
  ],
  devopsTools: [
    { tool: 'AWS', percentage: 48.62 },
    { tool: 'Azure', percentage: 26.03 },
    { tool: 'GCP', percentage: 23.86 },
    { tool: 'DigitalOcean', percentage: 10.45 },
    { tool: 'Heroku', percentage: 8.12 },
  ],
};

async function queryLanguages(column: string, total: number): Promise<LanguageStat[]> {
  const rows = await AppDataSource.query(`
    SELECT unnest(${column}) as language, COUNT(*) as cnt
    FROM responses
    WHERE ${column} IS NOT NULL
    GROUP BY language
    ORDER BY cnt DESC
    LIMIT 8
  `);
  return rows.map((r: { language: string; cnt: string }) => ({
    language: r.language,
    percentage: parseFloat(((parseInt(r.cnt) / total) * 100).toFixed(2)),
  }));
}

async function querySalaryByRole(): Promise<RoleSalary[]> {
  const rows = await AppDataSource.query(`
    SELECT
      unnest(dev_type) as role,
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY converted_comp_yearly) as median_salary,
      COUNT(*) as count
    FROM responses
    WHERE converted_comp_yearly > 0
      AND converted_comp_yearly < 500000
      AND dev_type IS NOT NULL
    GROUP BY role
    ORDER BY median_salary DESC
    LIMIT 10
  `);
  return rows.map((r: { role: string; median_salary: string; count: string }) => ({
    role: r.role,
    medianSalary: Math.round(parseFloat(r.median_salary)),
    count: parseInt(r.count),
  }));
}

async function queryDevOps(total: number): Promise<DevOpsStat[]> {
  const rows = await AppDataSource.query(`
    SELECT unnest(devops_tools) as tool, COUNT(*) as cnt
    FROM responses
    WHERE devops_tools IS NOT NULL
    GROUP BY tool
    ORDER BY cnt DESC
    LIMIT 5
  `);
  return rows.map((r: { tool: string; cnt: string }) => ({
    tool: r.tool,
    percentage: parseFloat(((parseInt(r.cnt) / total) * 100).toFixed(2)),
  }));
}

export async function computeGlobalStats(): Promise<GlobalStats> {
  const countRow = await AppDataSource.query('SELECT COUNT(*) as total FROM responses');
  const total = parseInt(countRow[0].total);

  if (total === 0) return MOCK_STATS;

  const [avgRow] = await AppDataSource.query(`
    SELECT AVG(converted_comp_yearly) as avg_salary,
           AVG(CASE WHEN ai_tool_used THEN 1.0 ELSE 0.0 END) * 100 as ai_pct,
           AVG(CASE WHEN learn_code_online THEN 1.0 ELSE 0.0 END) * 100 as online_pct
    FROM responses
    WHERE converted_comp_yearly > 0 AND converted_comp_yearly < 500000
  `);

  const [topLangsUsed, topLangsWanted, salaryByRole, devopsTools] = await Promise.all([
    queryLanguages('languages_worked', total),
    queryLanguages('languages_wanted', total),
    querySalaryByRole(),
    queryDevOps(total),
  ]);

  return {
    totalRespondents: total,
    avgSalaryGlobal: Math.round(parseFloat(avgRow.avg_salary || '0')),
    aiToolAdoption: Math.round(parseFloat(avgRow.ai_pct || '0')),
    onlineLearners: Math.round(parseFloat(avgRow.online_pct || '0')),
    topLanguagesUsed: topLangsUsed,
    topLanguagesWanted: topLangsWanted,
    salaryByRole,
    devopsTools,
  };
}

export async function computeRegional() {
  const countRow = await AppDataSource.query('SELECT COUNT(*) as total FROM responses');
  if (parseInt(countRow[0].total) === 0) return [];

  return AppDataSource.query(`
    SELECT
      country,
      ROUND(AVG(converted_comp_yearly)) as avg_salary,
      COUNT(*) as respondent_count
    FROM responses
    WHERE converted_comp_yearly > 0
      AND converted_comp_yearly < 500000
      AND country IS NOT NULL
    GROUP BY country
    HAVING COUNT(*) > 50
    ORDER BY avg_salary DESC
    LIMIT 30
  `);
}
