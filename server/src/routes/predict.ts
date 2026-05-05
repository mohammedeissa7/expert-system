import { Router, Request, Response } from 'express';
import { runPrediction } from '../services/mlBridge';
import { PredictionInput } from '../../../shared/types';

const router = Router();

router.post('/', async (req: Request, res: Response) => {
  try {
    const input: PredictionInput = req.body;

    if (
      input.yearsExperience === undefined ||
      !input.education ||
      !input.devType
    ) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    const result = await runPrediction(input);
    return res.json({ data: result });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[/api/predict]', message);
    return res.status(500).json({ error: message });
  }
});

export default router;
