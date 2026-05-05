import { Router, Request, Response } from 'express';
import { getCached, setCache } from '../services/cacheService';
import { computeRegional } from '../services/statsQueries';

const router = Router();

router.get('/', async (_req: Request, res: Response) => {
  try {
    const cached = await getCached<unknown[]>('regional_stats');
    if (cached) return res.json({ data: cached });

    const data = await computeRegional();
    await setCache('regional_stats', data);
    return res.json({ data });
  } catch (err) {
    console.error('[/api/regional]', err);
    return res.status(500).json({ error: 'Failed to compute regional stats' });
  }
});

export default router;
