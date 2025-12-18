# Utiliser une image Python officielle
FROM python:3.10-slim

# Installer les dépendances système nécessaires pour Obspy et Matplotlib
RUN apt-get update && apt-get install -y \
    libxml2-dev libxslt-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Définir le dossier de travail
WORKDIR /code

# Copier le fichier des dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le reste du code
COPY . .

# Créer le dossier temporaire et donner les droits d'écriture
RUN mkdir -p Data_extraction_temp && chmod 777 Data_extraction_temp

# Lancer l'application sur le port 7860 (obligatoire pour Hugging Face)
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]