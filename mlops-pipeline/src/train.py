import warnings
warnings.filterwarnings("ignore")

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from src.config import (
    ARTIFACTS_DIR,
    ID_COLUMN,
    METRICS_PATH,
    MLFLOW_EXPERIMENTS,
    MLFLOW_TRACKING_URI,
    MODEL_PATH,
    RANDOM_STATE,
    TARGET,
    TEST_SIZE,
)
from src.data_loader import load_data
from src.features import build_preprocessor
from src.utils import save_json



def evaluate_model(model, X_test, y_test) -> dict:
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1_score": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_proba),
    }



def get_models() -> dict:
    return {
        "logistic_regression": LogisticRegression(random_state=RANDOM_STATE, max_iter=1000),
        "decision_tree": DecisionTreeClassifier(
            random_state=RANDOM_STATE,
            max_depth=5,
            min_samples_split=10,
        ),
        "random_forest": RandomForestClassifier(
            random_state=RANDOM_STATE,
            n_estimators=200,
            max_depth=8,
            min_samples_split=10,
            n_jobs=-1,
        ),
    }



def prepare_data(df: pd.DataFrame):
    X = df.drop(columns=[TARGET]).copy()
    if ID_COLUMN in X.columns:
        X = X.drop(columns=[ID_COLUMN])

    y = df[TARGET].copy()
    numeric_features = X.select_dtypes(include=["int64", "float64"]).columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        stratify=y,
        random_state=RANDOM_STATE,
    )
    return X_train, X_test, y_train, y_test, numeric_features



def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    df = load_data()
    X_train, X_test, y_train, y_test, numeric_features = prepare_data(df)
    preprocessor = build_preprocessor(numeric_features)

    best_model_name = None
    best_pipeline = None
    best_metrics = None
    best_score = -1.0

    for model_name, model in get_models().items():
        mlflow.set_experiment(MLFLOW_EXPERIMENTS[model_name])

        with mlflow.start_run(run_name=f"{model_name}_baseline"):
            pipeline = Pipeline(
                steps=[
                    ("preprocessor", preprocessor),
                    ("model", model),
                ]
            )
            pipeline.fit(X_train, y_train)
            metrics = evaluate_model(pipeline, X_test, y_test)

            mlflow.log_param("target", TARGET)
            mlflow.log_param("test_size", TEST_SIZE)
            mlflow.log_param("random_state", RANDOM_STATE)
            mlflow.log_param("model_name", model_name)
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(pipeline, artifact_path="model")

            score = metrics["roc_auc"]
            if score > best_score:
                best_score = score
                best_model_name = model_name
                best_pipeline = pipeline
                best_metrics = metrics

    joblib.dump(best_pipeline, MODEL_PATH)
    save_json({"best_model_name": best_model_name, **best_metrics}, METRICS_PATH)
    print({"best_model_name": best_model_name, **best_metrics})


if __name__ == "__main__":
    main()
