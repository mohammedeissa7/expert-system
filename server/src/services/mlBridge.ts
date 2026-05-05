import { spawn } from 'child_process';
import path from 'path';
import { PredictionInput, PredictionOutput } from '../../../shared/types';

const PYTHON = process.env.PYTHON_PATH || 'python';
const SCRIPT = path.resolve(
  process.env.ML_SCRIPT_PATH || path.join(__dirname, '../../../ml/scripts/predict.py'),
);

export function runPrediction(input: PredictionInput): Promise<PredictionOutput> {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON, [SCRIPT], {
      env: { ...process.env },
    });

    let stdout = '';
    let stderr = '';

    proc.stdin.write(JSON.stringify(input));
    proc.stdin.end();

    proc.stdout.on('data', (chunk) => { stdout += chunk; });
    proc.stderr.on('data', (chunk) => { stderr += chunk; });

    proc.on('close', (code) => {
      if (code !== 0) {
        console.error('[mlBridge] Python error:', stderr);
        return reject(new Error(`Python exited with code ${code}: ${stderr}`));
      }
      try {
        const result = JSON.parse(stdout) as PredictionOutput;
        resolve(result);
      } catch {
        reject(new Error(`Failed to parse prediction output: ${stdout}`));
      }
    });

    proc.on('error', reject);
  });
}
