"""Train shared-core models with this consumer's canonical goal-column aliases."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pitch_oracle_core import goal_models  # noqa: E402


_original_goals_frame_from_historical = goal_models.goals_frame_from_historical


def _goals_frame_from_consumer_history(frame):
    """Map the consumer's stable names to the core goal-model schema."""
    return _original_goals_frame_from_historical(
        frame.rename(
            columns={
                "MatchDate": "Date",
                "FullTimeHomeGoals": "FTHG",
                "FullTimeAwayGoals": "FTAG",
            }
        )
    )


goal_models.goals_frame_from_historical = _goals_frame_from_consumer_history

import train_models  # noqa: E402


if __name__ == "__main__":
    try:
        train_models.train_and_save_models()
    except KeyError as error:
        # Core 1.4.0 writes the Dixon-Coles files successfully, then its
        # human-readable summary incorrectly expects every metric to expose
        # ``accuracy``. Treat only that post-write formatting defect as benign.
        models_dir = Path(os.getenv("PITCH_ORACLE_MODELS_DIR", "models"))
        required = (
            "dixon_coles_goal_model.pkl",
            "dixon_coles_goal_model.json",
            "goal_model_metrics.json",
        )
        if error.args != ("accuracy",) or any(not (models_dir / name).is_file() for name in required):
            raise
        print("Dixon-Coles artifacts written; ignored core summary formatting error.")
