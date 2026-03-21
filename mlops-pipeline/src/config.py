from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

DATA_PATH = DATA_DIR / "Loan_Data.csv"
MODEL_PATH = ARTIFACTS_DIR / "best_model.joblib"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"

TARGET = "default"
ID_COLUMN = "customer_id"

RANDOM_STATE = 42
TEST_SIZE = 0.2

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
MLFLOW_EXPERIMENTS = {
    "logistic_regression": "loan_default_logistic_regression",
    "decision_tree": "loan_default_decision_tree",
    "random_forest": "loan_default_random_forest",
}
