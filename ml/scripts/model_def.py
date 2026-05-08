"""
Shared neural-network definition.
Imported by both train.py and predict.py so that joblib/pickle can always
resolve SalaryMLP to the same fully-qualified class name
(ml.scripts.model_def.SalaryMLP) regardless of which script runs first.
"""
import torch
import torch.nn as nn


class SalaryMLP(nn.Module):
    """
    Three-hidden-layer MLP with BatchNorm + Dropout for salary regression.
    Input:  n_features float32 features (StandardScaler-normalised).
    Output: single log1p(salary) value.
    """

    def __init__(self, n_features: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.3),

            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),

            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.1),

            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)
