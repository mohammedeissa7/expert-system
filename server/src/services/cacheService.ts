import { AppDataSource } from '../config/database';
import { DashboardCache } from '../entities/DashboardCache';

const CACHE_TTL_HOURS = 24;

export async function getCached<T>(key: string): Promise<T | null> {
  const repo = AppDataSource.getRepository(DashboardCache);
  const entry = await repo.findOneBy({ metricKey: key });
  if (!entry) return null;

  const ageHours =
    (Date.now() - new Date(entry.computedAt).getTime()) / 1000 / 3600;
  if (ageHours > CACHE_TTL_HOURS) return null;

  return entry.data as T;
}

export async function setCache(key: string, data: unknown): Promise<void> {
  const repo = AppDataSource.getRepository(DashboardCache);
  await repo.upsert(
    { metricKey: key, data, computedAt: new Date() },
    ['metricKey'],
  );
}

export async function invalidateCache(key?: string): Promise<void> {
  const repo = AppDataSource.getRepository(DashboardCache);
  if (key) {
    await repo.delete({ metricKey: key });
  } else {
    await repo.clear();
  }
}
