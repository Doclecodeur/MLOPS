import json
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

MODEL_PATH = Path("artifacts/best_model.joblib")
METRICS_PATH = Path("artifacts/metrics.json")

st.set_page_config(page_title="Prédiction défaut bancaire", layout="centered",page_icon="🏦")

st.markdown("<h1 style='text-align: center;'>🏦</h1>", unsafe_allow_html=True)
st.header("Prédiction du risque de défaut de paiement")

#  Chargement du modèle 
@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)

# Chargement des métriques 
@st.cache_data
def load_metrics():
    with open(METRICS_PATH, "r") as f:
        return json.load(f)

model   = load_model()
metrics = load_metrics()

# Affichage 
st.markdown("<h4>Performance du meilleur modèle</h4>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Accuracy",  f"{metrics['accuracy']:.2%}")
col2.metric("Precision", f"{metrics['precision']:.2%}")
col3.metric("Recall",    f"{metrics['recall']:.2%}")
col4.metric("F1-Score",  f"{metrics['f1_score']:.2%}")

st.markdown("---")

metrics_df = pd.DataFrame({
    "Métrique": [
        "Meilleur modèle",
        "Accuracy",
        "Precision",
        "Recall",
        "F1-Score",
        "ROC-AUC",
    ],
    "Valeur": [
        metrics["best_model_name"].replace("_", " ").title(),
        f"{metrics['accuracy']:.2%}",
        f"{metrics['precision']:.2%}",
        f"{metrics['recall']:.2%}",
        f"{metrics['f1_score']:.2%}",
        f"{metrics['roc_auc']:.4f}",
    ],
    "Interprétation": [
        "Algorithme sélectionné automatiquement",
        "Taux de prédictions correctes",
        "Taux de vrais défauts parmi les alertes",
        "Taux de défauts réels détectés",
        "Équilibre Precision / Recall",
        "Capacité de discrimination globale",
    ],
})

st.dataframe(metrics_df, use_container_width=True, hide_index=True)

st.markdown("<h4 style='text-align: center;'>Saisissez les informations du client \
            puis lancez la prédiction.</h4>", unsafe_allow_html=True)

credit_lines_outstanding = st.number_input("Nombre de crédit", min_value=0, value=2)
loan_amt_outstanding = st.number_input("Montant du prêt restant", min_value=0.0, value=5000.0)
total_debt_outstanding = st.number_input("Dette totale restante", min_value=0.0, value=12000.0)
income = st.number_input("Revenu annuel", min_value=0.0, value=35000.0)
years_employed = st.number_input("Ancienneté professionnelle (années)", min_value=0.0, value=5.0)
fico_score = st.number_input("Score FICO", min_value=300, max_value=850, value=620)

if st.button("Prédire"):
    input_df = pd.DataFrame([
        {
            "credit_lines_outstanding": credit_lines_outstanding,
            "loan_amt_outstanding": loan_amt_outstanding,
            "total_debt_outstanding": total_debt_outstanding,
            "income": income,
            "years_employed": years_employed,
            "fico_score": fico_score,
        }
    ])

    probability = float(model.predict_proba(input_df)[0, 1])
    prediction = int(model.predict(input_df)[0])

    st.write(f"**Probabilité éstimée :** {probability:.2%}")
    
    if prediction == 1:
        st.error(
            f"Ce client présente un risque élevé de défaut de paiement "
            f"avec une probabilité de **{probability:.2%}**. "
            f"Il est recommandé de **refuser le prêt** ou d'exiger des garanties supplémentaires."
        )
    else:
        st.success(
            f"Ce client présente un faible risque de défaut de paiement "
            f"avec une probabilité de **{probability:.2%}**. "
            f"Le dossier peut être **accepté** en toute sécurité."
        )

    # Détail de la probabilité 
    st.info(
        f"Le modèle estime que ce client a **{probability:.2%}** de chances "
        f"de ne pas rembourser son prêt. "
        f"Le seuil de décision est fixé à **50%**."
    )