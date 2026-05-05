import { GlobalStats, PredictionInput, PredictionOutput, RegionalStat } from '../types';

const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.statusText}`);
  const json = await res.json();
  return (json.data ?? json) as T;
}

async function post<TIn, TOut>(path: string, body: TIn): Promise<TOut> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API POST ${path} failed: ${res.statusText}`);
  const json = await res.json();
  return (json.data ?? json) as TOut;
}

export const api = {
  getStats:    ()                          => get<GlobalStats>('/stats'),
  getRegional: ()                          => get<RegionalStat[]>('/regional'),
  predict:     (input: PredictionInput)    => post<PredictionInput, PredictionOutput>('/predict', input),
};
