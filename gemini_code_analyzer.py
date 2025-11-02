# gemini_code_analyzer.py

import os # FIX CRITIQUE: Ajout de l'import os
import sys
import subprocess
import json
import yaml 
import copy 
import hashlib 
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv
from tqdm import tqdm 

# --- CODES COULEUR ANSI ---
COLOR_GREEN = '\033[92m'
COLOR_RED = '\033[91m'
COLOR_YELLOW = '\033[93m'
COLOR_BLUE = '\033[94m'
COLOR_END = '\033[0m'

# --- Configuration par défaut et globale ---
CONFIG_FILE = '.geminianalyzer.yml'
CACHE_FILE = '.gemini_cache.json' # Fichier de cache local

# --- Fonctions de Configuration et d'Utilité ---

def deep_merge_dicts(base, override):
    """
    Fusionne récursivement le dictionnaire 'override' dans le dictionnaire 'base'.
    Les valeurs de 'override' prévalent en cas de conflit.
    """
    for key, value in override.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            base[key] = deep_merge_dicts(base[key], value)
        else:
            base[key] = value
    return base

def load_config():
    """Charge la configuration depuis .geminianalyzer.yml ou utilise les valeurs par défaut."""
    default_config = {
        'analyzer': {
            'model_name': 'gemini-2.5-flash',
            'max_file_size_kb': 500,
            # NOUVEAU: Si True, une sortie non taguée de l'IA bloque le push.
            'strict_untagged_output': False, 
            'analyzable_extensions': ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss', '.java', '.c', '.cpp', '.php', '.go', '.rb', '.sh', '.json', '.yml', '.yaml'],
        },
        'rules_override': "Aucune règle spécifique n'a été fournie."
    }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            user_config = yaml.safe_load(f)
        
        merged_config = copy.deepcopy(default_config)
        
        if user_config and isinstance(user_config, dict):
            return deep_merge_dicts(merged_config, user_config)
        
        return default_config
    except FileNotFoundError:
        print(f"{COLOR_YELLOW}WARN:{COLOR_END} Fichier de configuration '{CONFIG_FILE}' non trouvé. Utilisation des paramètres par défaut.", file=sys.stderr)
        return default_config
    except yaml.YAMLError as e: 
        print(f"{COLOR_RED}ERREUR CONFIG:{COLOR_END} Erreur de lecture YAML: {e}. Utilisation des paramètres par défaut.", file=sys.stderr)
        return default_config
    except Exception as e:
        print(f"{COLOR_RED}ERREUR CONFIG:{COLOR_END} Erreur inattendue lors du chargement de la configuration: {e}. Utilisation des paramètres par défaut.", file=sys.stderr)
        return default_config

def get_project_context():
    """Détecte les frameworks principaux pour fournir du contexte à Gemini."""
    context = ""
    if os.path.exists('package.json'):
        try:
            with open('package.json', 'r') as f:
                data = json.load(f)
            dependencies = list(data.get('dependencies', {}).keys())
            
            if 'react' in dependencies or 'next' in dependencies:
                context += "Le projet est un projet web front-end, probablement React/Next.js. Les fichiers JavaScript doivent respecter les règles des hooks et des composants fonctionnels."
            elif 'express' in dependencies:
                context += "Le projet est un projet Node.js/Express. Les bonnes pratiques du serveur (gestion des routes, sécurité) sont prioritaires."
            else:
                context += f"Le projet utilise Node.js avec les dépendances principales: {', '.join(dependencies[:5])}."
        except (json.JSONDecodeError, IOError):
            pass 
    if os.path.exists('requirements.txt'):
        context += " Le projet utilise Python. Les règles de la PEP 8 et l'efficacité du code sont importantes."
    if not context:
        context = "Aucun framework détecté. Analyse selon les standards généraux du langage."
    return context


# --- Fonctions de Cache ---

def load_cache():
    """Charge le cache depuis le fichier JSON. Nécessite os.path.exists."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_cache(cache_data):
    """Sauvegarde les données de cache dans le fichier JSON."""
    try:
        # Note : Le fichier de cache (.gemini_cache.json) DOIT être ignoré par Git via .gitignore
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=4)
    except IOError as e:
        print(f"{COLOR_RED}ERREUR CACHE:{COLOR_END} Impossible de sauvegarder le cache: {e}", file=sys.stderr)

def get_file_hash(file_path):
    """Génère le hash SHA256 du contenu d'un fichier."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f: # Lire en mode binaire
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except (IOError, OSError): # FIX WARNING: Gestion spécifique des exceptions d'E/S
        return None

# --- Fonctions d'Analyse ---

def get_files_and_patches(config):
    """
    Récupère la liste de tous les fichiers modifiés, filtre selon la config, 
    et génère le patch (avec fallback vers l'analyse complète).
    """
    files_to_process = []
    
    try:
        command = ["git", "diff", "--name-only", "origin/main...HEAD"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        files = result.stdout.strip().split('\n')
    except subprocess.CalledProcessError:
        try:
            command = ["git", "diff", "--name-only", "HEAD^", "HEAD"]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            files = result.stdout.strip().split('\n')
        except Exception:
            return []

    for file_path in files:
        if not file_path: continue
        
        analyzable_exts = config['analyzer']['analyzable_extensions']
        max_size_kb = config['analyzer']['max_file_size_kb']

        if not any(file_path.lower().endswith(ext) for ext in analyzable_exts): continue
            
        try:
            file_size_kb = os.path.getsize(file_path) / 1024
            if file_size_kb > max_size_kb:
                print(f"{COLOR_BLUE}INFO:{COLOR_END} Fichier ignoré (taille > {max_size_kb}KB): {file_path}", file=sys.stderr)
                continue
        except FileNotFoundError: continue

        # Analyse Différentielle : Tentative de patch puis Fallback
        try:
            patch_command = ["git", "diff", "--unified=0", "HEAD^", "--", file_path]
            patch_result = subprocess.run(patch_command, capture_output=True, text=True, check=True, errors='ignore')
            patch_content = patch_result.stdout.strip()
            
            if patch_content:
                files_to_process.append({ 'path': file_path, 'patch': patch_content })
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    full_content = f.read()
                
                if full_content.strip():
                    files_to_process.append({ 
                        'path': file_path, 
                        'patch': full_content 
                    })
                    print(f"{COLOR_YELLOW}WARN:{COLOR_END} Pas de patch détecté pour {file_path}. Analyse complète du fichier.", file=sys.stderr)

        except subprocess.CalledProcessError:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    full_content = f.read()
                
                if full_content.strip():
                    files_to_process.append({
                        'path': file_path,
                        'patch': full_content 
                    })
                    print(f"{COLOR_YELLOW}WARN:{COLOR_END} Impossible de générer le patch pour {file_path}. Analyse du fichier entier.", file=sys.stderr)
            except Exception:
                continue 

    return files_to_process


def analyze_code_with_gemini(file_info, config, context, cache):
    """Analyse le patch avec Gemini, en utilisant le cache si possible."""
    
    # FIX CRITIQUE: Extraction du chemin du fichier depuis file_info
    file_path = file_info['path'] 
    
    patch_content = file_info['patch']
    current_hash = get_file_hash(file_path)
    
    # 1. VÉRIFICATION DU CACHE ♻️
    if current_hash and file_path in cache and cache[file_path]['sha256'] == current_hash and cache[file_path]['status'] == 'CODE_VALIDÉ':
        return "CODE_VALIDÉ", True 

    # 2. AUCUN CACHE ou CACHE INVALIDE: Procède à l'analyse Gemini
    
    rules_override = config.get('rules_override', "Aucune règle spécifique n'a été fournie.")

    prompt = (
        "En tant qu'expert en revue de code pour le projet ayant le contexte suivant: (" + context + "). "
        # ... (reste du prompt inchangé) ...
        "Analyse les MODIFICATIONS (patch) fournies pour le fichier '" + file_path + "'. "
        
        "**Règles du Projet :** " + rules_override + " "
        
        "**Ton analyse doit obligatoirement classer chaque problème en deux niveaux :** "
        "1. **[CRITICAL_ERROR]** : Erreur de syntaxe, faille de sécurité, bug fonctionnel évident, ou non-conformité à une règle critique. (DOIT bloquer le push) "
        "2. **[WARNING]** : Problème de style, d'optimisation mineure ou non-conformité à une bonne pratique non critique. (PEUT être ignoré, mais doit être signalé) "
        
        "Si les changements sont techniquement sains, réponds UNIQUEMENT par la chaîne 'CODE_VALIDÉ'."
        "Sinon, liste CLAIREMENT TOUS les problèmes trouvés en commençant chaque entrée par son tag ([CRITICAL_ERROR] ou [WARNING]). "
        "Propose ensuite une correction de code complète ou des suggestions claires pour chaque problème. "
        f"Voici les modifications (patch):\n\n"
        f"```diff\n{patch_content}\n```"
    )
    
    # Appel à l'API
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=config['analyzer']['model_name'],
            contents=prompt
        )
        result = response.text.strip()
        
        # 3. MISE À JOUR DU CACHE
        if "CODE_VALIDÉ" in result:
            cache[file_path] = {'sha256': current_hash, 'status': 'CODE_VALIDÉ'}
        else:
            if file_path in cache:
                 del cache[file_path]
            
        return result, False
        
    except APIError as e:
        return f"{COLOR_RED}Erreur API Gemini:{COLOR_END} {e}. Vérifiez votre clé API ou votre quota.", False
    except Exception as e:
        return f"{COLOR_RED}Erreur inattendue:{COLOR_END} {e}", False

# --------------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------------

def main():
    
    load_dotenv()
    config = load_config()
    context = get_project_context()
    
    cache = load_cache() 
    
    if not os.getenv("GEMINI_API_KEY"):
        print(f"\n{COLOR_RED}🛑 ERREUR CRITIQUE:{COLOR_END} La variable d'environnement GEMINI_API_KEY n'est pas définie.", file=sys.stderr)
        print(f"Veuillez la définir (par exemple, dans un fichier .env à la racine du projet).", file=sys.stderr)
        sys.exit(1)

    print(f"{COLOR_BLUE}--- 🚀 Démarrage de l'analyse de code par Gemini (pre-push) ---{COLOR_END}")
    print(f"{COLOR_BLUE}Contexte du Projet: {COLOR_END}{context}")
    
    files_to_analyze = get_files_and_patches(config)
    
    if not files_to_analyze:
        print(f"\n{COLOR_YELLOW}--- INFO HOOK : Aucun fichier pertinent trouvé. Poursuite du push. ---{COLOR_END}")
        sys.exit(0)
    
    has_critical_error = False
    
    print(f"{COLOR_BLUE}Fichiers à analyser ({len(files_to_analyze)}) : {COLOR_END}{', '.join([f['path'] for f in files_to_analyze])}")

    progress_bar = tqdm(
        files_to_analyze, 
        desc=f"{COLOR_BLUE}Analyse en cours{COLOR_END}", 
        unit="file", 
        ncols=100,
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
    )
    
    # Boucle d'analyse
    for file_info in progress_bar:
        # FIX CRITIQUE: Extraction du chemin du fichier depuis file_info
        file_path = file_info['path'] 
        
        progress_bar.set_description(f"Analyse de {file_path.split('/')[-1]}")
        result, is_cached = analyze_code_with_gemini(file_info, config, context, cache) 
        
        progress_bar.clear()
        
        # Logique de gestion du cache
        if is_cached:
            print(f"[{COLOR_BLUE}♻️ CACHE{COLOR_END}] {file_path} : Validation réutilisée (Hash inchangé).")
        # Logique de classification si l'analyse a été effectuée
        elif "CODE_VALIDÉ" in result:
            print(f"[{COLOR_GREEN}✅{COLOR_END}] {file_path} : Code validé par Gemini.")
        else:
            # Recherche des erreurs critiques
            if "[CRITICAL_ERROR]" in result:
                print(f"[{COLOR_RED}🛑{COLOR_END}] {file_path} : {COLOR_RED}ERREURS CRITIQUES DÉTECTÉES !{COLOR_END}")
                has_critical_error = True
            elif "[WARNING]" in result:
                print(f"[{COLOR_YELLOW}⚠️{COLOR_END}] {file_path} : {COLOR_YELLOW}Avertissements de style/optimisation !{COLOR_END}")
            else:
                 # Logique de gestion de l'output non tagué (Correction de sécurité via la configuration)
                is_strict = config['analyzer'].get('strict_untagged_output', False)

                if is_strict:
                    print(f"[{COLOR_RED}❌{COLOR_END}] {file_path} : {COLOR_RED}PROBLÈME DÉTECTÉ (Output IA non classifié - Mode strict) !{COLOR_END}")
                    print(f"{COLOR_RED}Le format de réponse de l'IA n'était pas respecté. Push bloqué par sécurité.{COLOR_END}")
                    has_critical_error = True # BLOQUE le push
                else:
                    print(f"[{COLOR_YELLOW}⚠️{COLOR_END}] {file_path} : {COLOR_YELLOW}Avertissements (non classifiés, mode non strict) !{COLOR_END}")

            print("-" * 50)
            print(result)
            print("-" * 50)
        
        progress_bar.display()

    progress_bar.close()
    
    save_cache(cache)

    # Décision finale du push : Bloque uniquement si CRITICAL_ERROR est trouvé
    if has_critical_error:
        print(f"\n{COLOR_RED}!!! 🛑 PUSH ANNULÉ : Des ERREURS CRITIQUES ont été détectées. !!!{COLOR_END}")
        sys.exit(1) 
    else:
        print(f"\n{COLOR_GREEN}--- ✅ Analyse terminée. Code propre (ou seulement des avertissements). Poursuite du push. ---{COLOR_END}")
        sys.exit(0)

if __name__ == "__main__":
    main()