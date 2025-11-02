# 📌 Calculatrice & Convertisseur (Python)

Ce projet est une application python permettant :

🧮 Calculatrice sécurisée 
📏 Conversion d’unités 
💱 Conversion de devises 
🧠 Code Python typé (type hints) et structuré en modules

📁 Structure du projet
calculatrice_convertisseur/
│
├── main.py
├── requirements.txt
│
├── converters/
│   ├── __init__.py
│   ├── units.py
│   └── currency.py
│
└── calculator/
    ├── __init__.py
    └── safe_eval.py

✅ Prérequis

Python 3.10+


# 🛠️ Installation

1️⃣ Ouvrir le dossier du projet
cd chemin/vers/calculatrice_convertisseur

# Configuration de l'Environnement Python

Il est fortement recommandé d'utiliser un environnement virtuel (venv) pour isoler les dépendances du projet.

Créez et activez l'environnement virtuel :

Bash

python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# ou
.\venv\Scripts\activate    # Windows
Installez les dépendances nécessaires (SDK Google GenAI et python-dotenv) :



# 2️⃣ Installer les dépendances

Windows (PowerShell) :

python -m pip install -r requirements.txt


Mac / Linux :

pip install -r requirements.txt


Si pip n'est pas reconnu sur Windows, essaye :

py -m pip install -r requirements.txt

# 🚀 Lancer l'application
python main.py


Ou :

py main.py