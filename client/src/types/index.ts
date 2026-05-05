// Shared TypeScript types (client-side copy)
export interface LanguageStat {
  language: string;
  percentage: number;
}

export interface RoleSalary {
  role: string;
  medianSalary: number;
  count: number;
}

export interface DevOpsStat {
  tool: string;
  percentage: number;
}

export interface GlobalStats {
  totalRespondents: number;
  avgSalaryGlobal: number;
  aiToolAdoption: number;
  onlineLearners: number;
  topLanguagesUsed: LanguageStat[];
  topLanguagesWanted: LanguageStat[];
  salaryByRole: RoleSalary[];
  devopsTools: DevOpsStat[];
}

export interface PredictionInput {
  yearsExperience: number;
  education: 'bachelors' | 'masters' | 'phd' | 'bootcamp' | 'self-taught';
  devType: string;
  skills: string[];
  country?: string;
}

export interface PredictionOutput {
  predictedSalary: number;
  confidenceLow: number;
  confidenceHigh: number;
  comparableRoles: RoleSalary[];
  missingHighValueSkills: string[];
  shapExplanation: Record<string, number>;
  source?: string;
}

export interface RegionalStat {
  country: string;
  avg_salary: number;
  respondent_count: number;
}
