# README — Pipeline MLOps complet

Ce document explique comment mettre en place le pipeline suivant :

Git push  
→ GitHub Actions  
→ installation des dépendances  
→ tests automatiques  
→ entraînement du modèle  
→ tracking MLflow  
→ build Docker  
→ push vers Google Artifact Registry  
→ déploiement sur Google Cloud Run

## 1. Prérequis

Installez localement :

- Python 3.11
- Git
- Docker
- Google Cloud SDK (`gcloud`)
- un compte GitHub
- un projet Google Cloud

Activez ensuite les API utiles dans votre projet Google Cloud :

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com
```

## 2. Variables à définir

Adaptez ces variables à votre projet :

```bash
export PROJECT_ID="votre-project-id"
export REGION="europe-west1"
export GAR_REPOSITORY="loan-default-repo"
export SERVICE_NAME="loan-default-streamlit"
export WIF_POOL="github"
export WIF_PROVIDER="github-provider"
export GITHUB_REPO="OWNER/REPO"
export SERVICE_ACCOUNT_NAME="github-actions-deployer"
export SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
```

## 3. Créer le dépôt Artifact Registry

Créez un dépôt Docker régional :

```bash
gcloud artifacts repositories create "$GAR_REPOSITORY" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Docker repository for loan default MLOps project"
```

L’image sera ensuite poussée vers une URL de la forme :

```bash
${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPOSITORY}/loan-default-app:TAG
```

## 4. Créer le service account GitHub Actions

```bash
gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
  --display-name="GitHub Actions deployer"
```

Attribuez les rôles nécessaires :

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
```

## 5. Configurer Workload Identity Federation pour GitHub Actions

### 5.1 Créer le pool

```bash
gcloud iam workload-identity-pools create "$WIF_POOL" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

Récupérez son nom complet :

```bash
export WIF_POOL_ID=$(gcloud iam workload-identity-pools describe "$WIF_POOL" \
  --project="$PROJECT_ID" \
  --location="global" \
  --format="value(name)")
```

### 5.2 Créer le provider GitHub

```bash
gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$WIF_POOL" \
  --display-name="GitHub provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner"
```

Récupérez le nom complet du provider :

```bash
export WIF_PROVIDER_FULL=$(gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$WIF_POOL" \
  --format="value(name)")
```

### 5.3 Autoriser votre dépôt GitHub à utiliser le service account

```bash
gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WIF_POOL_ID}/attribute.repository/${GITHUB_REPO}"
```

## 6. Secrets GitHub à créer

Dans votre dépôt GitHub, ouvrez **Settings > Secrets and variables > Actions** puis ajoutez :

- `GCP_PROJECT_ID` = votre project id
- `GCP_REGION` = votre région, par exemple `europe-west1`
- `GAR_REPOSITORY` = le nom du dépôt Artifact Registry
- `GCP_SERVICE_ACCOUNT` = l’email du service account
- `WIF_PROVIDER` = le nom complet du provider
- `MLFLOW_TRACKING_URI` = l’URL de votre serveur MLflow, si vous utilisez un serveur distant

Exemple de valeur pour `WIF_PROVIDER` :

```bash
projects/123456789/locations/global/workloadIdentityPools/github/providers/github-provider
```

## 7. Initialiser le projet Git localement

```bash
git init
git branch -M main
git add .
git commit -m "Initial commit - MLOps loan default project"
git remote add origin https://github.com/OWNER/REPO.git
git push -u origin main
```

## 8. Vérification locale avant GitHub Actions

Créez un environnement virtuel, installez les dépendances puis lancez les tests et l’entraînement :

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pytest -q
python -m src.train
```

Lancez ensuite MLflow localement :

```bash
mlflow ui
```

Puis Streamlit :

```bash
streamlit run app/streamlit_app.py
```

## 9. Workflow GitHub Actions

Le fichier `.github/workflows/ci-cd.yml` peut être celui-ci :

```yaml
name: CI-CD-Loan-Default-MLops

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: ${{ secrets.GCP_REGION }}
  GAR_REPOSITORY: ${{ secrets.GAR_REPOSITORY }}
  SERVICE_NAME: loan-default-streamlit
  MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}

jobs:
  ci:
    name: Tests et entraînement
    runs-on: ubuntu-latest

    steps:
      - name: Checkout du code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Installer les dépendances
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Lancer les tests
        run: pytest -q

      - name: Entraîner le modèle
        run: python -m src.train

      - name: Sauvegarder les artefacts
        uses: actions/upload-artifact@v4
        with:
          name: model-artifacts
          path: artifacts/

  cd:
    name: Build Docker et déploiement Cloud Run
    needs: ci
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout du code
        uses: actions/checkout@v4

      - name: Télécharger les artefacts
        uses: actions/download-artifact@v4
        with:
          name: model-artifacts
          path: artifacts/

      - name: Authentification GCP
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Setup gcloud
        uses: google-github-actions/setup-gcloud@v2

      - name: Docker auth pour Artifact Registry
        run: gcloud auth configure-docker ${{ env.REGION }}-docker.pkg.dev --quiet

      - name: Build image Docker
        run: |
          docker build -t ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.GAR_REPOSITORY }}/loan-default-app:${{ github.sha }} .

      - name: Push image Docker
        run: |
          docker push ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.GAR_REPOSITORY }}/loan-default-app:${{ github.sha }}

      - name: Déploiement Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE_NAME }}
          region: ${{ env.REGION }}
          image: ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.GAR_REPOSITORY }}/loan-default-app:${{ github.sha }}
```

## 10. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

## 11. Tracking MLflow

Si vous utilisez un serveur MLflow distant, définissez :

```bash
export MLFLOW_TRACKING_URI="http://IP_OU_DNS:5000"
```

Ou dans GitHub Secrets :

- `MLFLOW_TRACKING_URI`

Dans votre code Python, vous pouvez soit laisser MLflow lire la variable d’environnement, soit définir explicitement :

```python
import os
import mlflow

tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
if tracking_uri:
    mlflow.set_tracking_uri(tracking_uri)
```

## 12. Déploiement manuel de secours sur Cloud Run

Si vous voulez tester sans GitHub Actions :

```bash
gcloud auth login
gcloud config set project "$PROJECT_ID"
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPOSITORY}/loan-default-app:manual .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPOSITORY}/loan-default-app:manual

gcloud run deploy "$SERVICE_NAME" \
  --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPOSITORY}/loan-default-app:manual" \
  --platform=managed \
  --region="$REGION" \
  --allow-unauthenticated
```

## 13. Vérifications après déploiement

Pour lister les services Cloud Run :

```bash
gcloud run services list --region="$REGION"
```

Pour décrire le service :

```bash
gcloud run services describe "$SERVICE_NAME" --region="$REGION"
```

Pour voir les images du dépôt :

```bash
gcloud artifacts docker images list \
  ${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPOSITORY}
```

## 14. Résultat attendu

À chaque `git push` sur `main` :

1. GitHub Actions récupère le code.
2. Python 3.11 est installé.
3. Les dépendances sont installées.
4. Les tests `pytest` sont exécutés.
5. Le modèle est entraîné.
6. Les métriques et modèles sont envoyés à MLflow.
7. L’image Docker est construite.
8. L’image est poussée vers Artifact Registry.
9. Cloud Run est redéployé avec cette nouvelle image.

## 15. Problèmes fréquents

### Erreur d’authentification GitHub → GCP
Vérifiez :

- le `WIF_PROVIDER`
- le `GCP_SERVICE_ACCOUNT`
- le binding `roles/iam.workloadIdentityUser`
- la valeur exacte de `GITHUB_REPO`

### Erreur Docker push denied
Vérifiez :

- le rôle `roles/artifactregistry.writer`
- la région du dépôt
- la commande `gcloud auth configure-docker`

### Erreur Cloud Run deploy denied
Vérifiez :

- le rôle `roles/run.admin`
- le rôle `roles/iam.serviceAccountUser`

### MLflow n’enregistre rien
Vérifiez :

- la variable `MLFLOW_TRACKING_URI`
- l’accessibilité réseau du serveur MLflow
- que votre script appelle bien `mlflow.start_run()` et `mlflow.log_metrics()`
