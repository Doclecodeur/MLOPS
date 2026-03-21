from src.data_loader import load_data
from src.train import prepare_data


def test_data_loading():
    df = load_data()
    assert not df.empty
    assert "default" in df.columns



def test_prepare_data():
    df = load_data()
    X_train, X_test, y_train, y_test, numeric_features = prepare_data(df)
    assert len(X_train) > 0
    assert len(X_test) > 0
    assert len(y_train) > 0
    assert len(y_test) > 0
    assert len(numeric_features) > 0
