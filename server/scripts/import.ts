import 'reflect-metadata';
import fs from 'fs';
import path from 'path';
import { parse } from 'csv-parse';
import dotenv from 'dotenv';
import { AppDataSource } from '../src/config/database';
import { SurveyResponse } from '../src/entities/SurveyResponse';

dotenv.config();

const CSV_PATH = path.resolve(
  process.env.CSV_PATH || path.join(__dirname, '../../data/survey_results_public.csv'),
);
const BATCH_SIZE = 1000;
const SALARY_MAX = 500_000;

function parseArray(val: string): string[] {
  if (!val || val === 'NA') return [];
  return val.split(';').map((s) => s.trim()).filter(Boolean);
}

function parseYears(val: string): number | null {
  if (!val || val === 'NA' || val === 'More than 50 years') return null;
  const n = parseInt(val);
  return isNaN(n) ? null : n;
}

function parseSalary(val: string): number | null {
  if (!val || val === 'NA') return null;
  const n = parseFloat(val);
  if (isNaN(n) || n <= 0 || n > SALARY_MAX) return null;
  return n;
}

async function runImport() {
  if (!fs.existsSync(CSV_PATH)) {
    console.error(`❌ CSV not found at: ${CSV_PATH}`);
    console.error('   Place survey_results_public.csv in the /data folder.');
    process.exit(1);
  }

  await AppDataSource.initialize();
  console.log('✅ DB connected');

  const repo = AppDataSource.getRepository(SurveyResponse);
  await repo.clear(); // Start fresh
  console.log('🗑️  Cleared existing responses');

  let batch: Partial<SurveyResponse>[] = [];
  let total = 0;
  let skipped = 0;

  const parser = fs.createReadStream(CSV_PATH).pipe(
    parse({ columns: true, skip_empty_lines: true, trim: true }),
  );

  for await (const row of parser) {
    const salary = parseSalary(row['ConvertedCompYearly']);

    const record: Partial<SurveyResponse> = {
      respondentId: parseInt(row['ResponseId']) || undefined,
      country: row['Country'] !== 'NA' ? row['Country'] : undefined,
      yearsCodePro: parseYears(row['YearsCodePro']) ?? undefined,
      devType: parseArray(row['DevType']),
      languagesWorked: parseArray(row['LanguageHaveWorkedWith']),
      languagesWanted: parseArray(row['LanguageWantToWorkWith']),
      devopsTools: parseArray(row['PlatformHaveWorkedWith']),
      convertedCompYearly: salary ?? undefined,
      edLevel: row['EdLevel'] !== 'NA' ? row['EdLevel'] : undefined,
      aiToolUsed: row['AISearchHaveWorkedWith']?.length > 0,
      learnCodeOnline:
        (row['LearnCode'] || '').toLowerCase().includes('online'),
    };

    batch.push(record);

    if (batch.length >= BATCH_SIZE) {
      await repo.insert(batch as SurveyResponse[]);
      total += batch.length;
      console.log(`  Inserted ${total} rows...`);
      batch = [];
    }
  }

  if (batch.length > 0) {
    await repo.insert(batch as SurveyResponse[]);
    total += batch.length;
  }

  console.log(`\n✅ Import complete: ${total} rows inserted, ${skipped} skipped`);

  // Invalidate cache
  await AppDataSource.query("DELETE FROM dashboard_cache");
  console.log('🔄 Cache invalidated');

  await AppDataSource.destroy();
}

runImport().catch((err) => {
  console.error('Import failed:', err);
  process.exit(1);
});
