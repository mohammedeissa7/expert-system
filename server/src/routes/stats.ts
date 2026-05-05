import { Router, Request, Response } from 'express';
import { getCached, setCache } from '../services/cacheService';
import { computeGlobalStats } from '../services/statsQueries';
import { GlobalStats } from '../../../shared/types';

const router = Router();

router.get('/', async (_req: Request, res: Response) => {
  try {
    const cached = await getCached<GlobalStats>('global_stats');
    if (cached) return res.json({ data: cached, source: 'cache' });

    const stats = await computeGlobalStats();
    await setCache('global_stats', stats);
    return res.json({ data: stats, source: 'computed' });
  } catch (err) {
    console.error('[/api/stats]', err);
    return res.status(500).json({ error: 'Failed to compute stats' });
  }
});

export default router;
