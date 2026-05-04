export type ChartView = "used" | "want";

export type RegionFilter = "global" | "usa" | "europe" | `country:${string}`;

export interface ImportSurveyRequest {
  publicCsvPath: string;
  schemaCsvPath: string;
}

export interface ImportSurveyResponse {
  status: "success" | "error";
  importedRows: number;
  schemaRows: number;
  fieldsDetected: number;
  aggregatesBuilt: number;
  warnings: string[];
}

export interface SummaryStat {
  label: string;
  value: string;
  detail: string;
}

export interface DashboardSummaryResponse {
  stats: SummaryStat[];
}

export interface RankedDatum {
  label: string;
  value: number;
}

export interface LanguagesResponse {
  view: ChartView;
  items: RankedDatum[];
}

export interface DevopsResponse {
  items: RankedDatum[];
}

export interface SalaryByRoleResponse {
  region: RegionFilter;
  items: RankedDatum[];
}

export interface AdvisorOptionsResponse {
  educationLevels: string[];
  developerTypes: string[];
  countries: string[];
  skills: string[];
  employmentOptions: string[];
}

export interface AdvisorPredictRequest {
  yearsExperience: number;
  education: string;
  developerType: string;
  country: string;
  region: RegionFilter;
  selectedSkills: string[];
  employment: string;
}

export interface RoleMatch {
  role: string;
  fitScore: number;
  medianSalary: number;
}

export interface LearningStep {
  title: string;
  rationale: string;
}

export interface AdvisorPredictResponse {
  predictedSalary: number;
  confidence: {
    low: number;
    high: number;
  };
  explanation: string[];
  roleMatches: RoleMatch[];
  missingSkills: string[];
  learningPath: LearningStep[];
}

export interface NormalizedSurveyResponse {
  respondentId: string;
  country: string;
  region: string;
  education: string;
  developerTypes: string[];
  employment: string;
  yearsCode: number | null;
  yearsCodePro: number | null;
  salaryUsd: number | null;
  languagesUsed: string[];
  languagesWanted: string[];
  devopsTools: string[];
  platforms: string[];
  aiTools: string[];
  learningSources: string[];
  raw: Record<string, string>;
}

