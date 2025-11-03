import os
import sys
import subprocess
import json
import yaml 
import copy 
import hashlib 
import smtplib 
import re 

from email.mime.text import MIMEText 
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv
from tqdm import tqdm 

# --- CODES COULEUR ANSI (pour l'affichage console local) ---
COLOR_GREEN = '\033[92m'
COLOR_RED = '\033[91m'
COLOR_YELLOW = '\033[93m'
COLOR_BLUE = '\033[94m'
COLOR_END = '\033[0m'

# --- Configuration par défaut et globale ---
CONFIG_FILE = '.geminianalyzer.yml'
CACHE_FILE = '.gemini_cache.json' 
EMAIL_PREFS_FILE = '.user_email_prefs.json'

# --- RÈGLES DE CODAGE DYNAMIQUES PAR DÉFAUT ---
LANGUAGE_RULES = {
    'Python': (
        "Le projet est en Python. Les règles sont : Utiliser le typage Python (Type Hinting) pour toutes les fonctions et variables majeures. "
        "Adhérer strictement à la PEP 8. Utiliser des f-strings pour le formatage de chaîne. Éviter les boucles O(n^2) inutiles."
    ),
    'JavaScript/TypeScript': (
        "Le projet est en JavaScript/TypeScript. Les règles sont : Préférer `const` et `let` à `var`. Utiliser des fonctions fléchées pour les callbacks. "
        "Gérer correctement les promesses (async/await). Respecter les règles des Hooks si React est détecté."
    ),
    'Java': (
        "Le projet est en Java. Les règles sont : Respecter les conventions de nommage Java (CamelCase pour les méthodes/variables, PascalCase pour les classes). "
        "Utiliser les annotations `@Override`. Assurer une bonne gestion des exceptions (try-with-resources)."
    ),
    'General': "Concentrez-vous sur la clarté du code, la gestion des erreurs, et l'optimisation des complexités algorithmiques."
}

# --- Fonctions de Configuration et d'Utilité (inchangées) ---

def deep_merge_dicts(base, override):
    """Fusionne récursivement le dictionnaire 'override' dans le dictionnaire 'base'."""
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
    except (FileNotFoundError, yaml.YAMLError, Exception) as e:
        print(f"{COLOR_RED}ERREUR CONFIG:{COLOR_END} Erreur de lecture YAML/Config: {e}. Utilisation des paramètres par défaut.", file=sys.stderr)
        return default_config

def load_user_prefs():
    """Charge les préférences utilisateur (email de repli et intérêt pour la personnalisation) en local."""
    if os.path.exists(EMAIL_PREFS_FILE):
        try:
            with open(EMAIL_PREFS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"{COLOR_YELLOW}WARN:{COLOR_END} Impossible de lire les préférences utilisateur. Utilisation par défaut.", file=sys.stderr)
            return {}
    return {}

def detect_project_language():
    """Détecte la langue principale du projet et retourne une étiquette et le contexte détaillé."""
    context = ""
    
    # 1. JavaScript/TypeScript
    if os.path.exists('package.json'):
        language_tag = 'JavaScript/TypeScript'
        context = "Projet Node.js/Web."
        
        if os.path.exists('tsconfig.json') or any(f.endswith(('.ts', '.tsx')) for f in os.listdir('.') if os.path.isfile(f)):
            context += " Le TypeScript est privilégié."
            
        try:
            with open('package.json', 'r') as f:
                data = json.load(f)
            dependencies = list(data.get('dependencies', {}).keys())
            if 'react' in dependencies or 'next' in dependencies:
                context += " Framework React/Next.js détecté. Les règles des Hooks sont cruciales."
        except:
            pass
        return language_tag, context

    # 2. Python
    if os.path.exists('requirements.txt') or os.path.exists('setup.py') or any(f.endswith('.py') for f in os.listdir('.') if os.path.isfile(f)):
        return 'Python', "Projet Python. L'analyse doit se concentrer sur la PEP 8, la performance et le typage."
        
    # 3. Java
    if any(f.endswith('.java') for f in os.listdir('.') if os.path.isfile(f)) or os.path.exists('pom.xml'):
        return 'Java', "Projet Java. L'analyse doit se concentrer sur les conventions Java et la gestion des ressources."
        
    # 4. Fallback
    return 'General', "Aucun langage principal détecté. Analyse selon les standards généraux du logiciel."

# --- Fonctions de Cache et d'Analyse (inchangées) ---

def load_cache():
    """Charge le cache depuis le fichier JSON."""
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
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=4)
    except IOError as e:
        print(f"{COLOR_RED}ERREUR CACHE:{COLOR_END} Impossible de sauvegarder le cache: {e}", file=sys.stderr)

def get_file_hash(file_path):
    """Génère le hash SHA256 du contenu d'un fichier."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f: 
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except (IOError, OSError): 
        return None

# MODIFIÉ : Mise à jour de la fonction pour utiliser le commit range du hook pre-push
def get_files_and_patches(config, refs_data=None):
    """
    Récupère la liste de tous les fichiers modifiés, filtre et génère le patch.
    Utilise refs_data (old_ref et new_ref) si fourni par le hook pre-push.
    """
    files_to_process = []
    
    # 1. DÉTERMINATION DE LA PLAGE DE COMMITS À ANALYSER
    
    if refs_data:
        # Mode pre-push: Analyse de la plage de commits envoyée via STDIN
        
        lines = refs_data.split('\n')
        # On cherche la dernière ligne significative pour extraire les SHAs (format: <local ref> <local sha> <remote ref> <remote sha>)
        last_ref = [x for x in lines if x.strip()][-1].split() if lines else []
        
        if len(last_ref) >= 4:
             # old_sha_for_diff est le SHA du dernier commit connu sur la remote (index 1)
             # new_sha_for_diff est le SHA du commit le plus récent à pousser (index 3)
             old_sha_for_diff = last_ref[1]
             new_sha_for_diff = last_ref[3]
             
             # Utilité : Si old_sha_for_diff est 0000... (nouvelle branche), on analyse tous les commits de cette branche
             if all(c == '0' for c in old_sha_for_diff):
                 commit_range = new_sha_for_diff # Analyse tous les commits de la nouvelle branche
             else:
                 # Standard push: compare entre old remote HEAD et new local HEAD
                 commit_range = f"{old_sha_for_diff}..{new_sha_for_diff}"
        else:
            print(f"{COLOR_YELLOW}WARN:{COLOR_END} Format de références pre-push inattendu. Utilisation de HEAD^...HEAD.", file=sys.stderr)
            commit_range = "HEAD^...HEAD"
            
    else:
        # Mode local (sans hook) ou CI/CD sans références de push explicites
        # Analyse du dernier commit ou de l'index
        commit_range = "HEAD^...HEAD" # Analyser les changements du dernier commit

    # 2. COMMANDE GIT DIFF
    try:
        # Récupère la liste des fichiers modifiés dans la plage de commits
        command_files = ["git", "diff", "--name-only", commit_range]
        result_files = subprocess.run(command_files, capture_output=True, text=True, check=True, timeout=10)
        files = result_files.stdout.strip().split('\n')
    except Exception as e:
        print(f"{COLOR_RED}ERREUR GIT:{COLOR_END} Échec de la commande 'git diff --name-only {commit_range}': {e}", file=sys.stderr)
        return []

    # 3. FILTRAGE ET RÉCUPÉRATION DU PATCH
    for file_path in files:
        if not file_path or not os.path.exists(file_path): continue
        
        analyzable_exts = config['analyzer']['analyzable_extensions']
        if not any(file_path.lower().endswith(ext) for ext in analyzable_exts): continue
            
        try:
            # Récupère le patch pour la plage de commits, mais uniquement pour le fichier en cours
            patch_command = ["git", "diff", "--unified=0", commit_range, "--", file_path]
            patch_result = subprocess.run(patch_command, capture_output=True, text=True, check=True, errors='ignore', timeout=10)
            patch_content = patch_result.stdout.strip()
            
            # Pour un fichier modifié, le patch doit contenir au moins le header du diff et des changements
            if patch_content.strip():
                files_to_process.append({ 'path': file_path, 'patch': patch_content })
        except Exception:
            continue

    return files_to_process

# --- Analyse Code avec Gemini (inchangée) ---
def analyze_code_with_gemini(file_info, config, context, cache, full_rules):
    """Analyse le patch avec Gemini, en utilisant le cache si possible."""
    
    file_path = file_info['path'] 
    patch_content = file_info['patch']
    current_hash = get_file_hash(file_path)
    
    # 1. VÉRIFICATION DU CACHE
    if current_hash and file_path in cache and cache[file_path]['sha256'] == current_hash and cache[file_path]['status'] == 'CODE_VALIDÉ':
        return "CODE_VALIDÉ", True 

    # 2. AUCUN CACHE: Procède à l'analyse Gemini
    
    prompt = (
        "En tant qu'expert en revue de code pour le projet ayant le contexte suivant: (" + context + "). "
        "Analyse les MODIFICATIONS (patch) fournies pour le fichier '" + file_path + "'. "
        
        "**Règles du Projet :** " + full_rules + " "
        
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


# --- Fonction d'Envoi d'E-mail (avec correction de style) ---

def send_push_rejection_email(recipient_email, reason_summary, detailed_report, user_prefs, user_name):
    """
    Envoie un e-mail au développeur avec le rapport de l'analyse, formaté en HTML stylisé.
    Le message est personnalisé selon l'intérêt de l'utilisateur (sans le mentionner).
    """
    
    # Récupération des détails SMTP (depuis l'environnement)
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT", 587)
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL", "gemini-analyzer@noreply.com")

    if not all([smtp_server, smtp_user, smtp_password]):
        print(f"{COLOR_YELLOW}WARN:{COLOR_END} Variables d'environnement SMTP manquantes. Email non envoyé.", file=sys.stderr)
        return

    # Personnalisation du message 
    interest = user_prefs.get('interest', 'la qualité du code')
    
    # --- 1. GÉNÉRATION DU MESSAGE MOTIVANT PAR GEMINI ---
    motivational_text = reason_summary
    
    try:
        client = genai.Client()
        
        prompt_motivation = (
            f"L'utilisateur a un intérêt personnel pour '{interest}'. "
            f"Le problème de code détecté est résumé par : '{reason_summary}'. "
            f"Rédige un court paragraphe (3-4 phrases maximum) pour une introduction d'e-mail. "
            f"Ce texte doit utiliser une ANALOGIE tirée de son centre d'intérêt pour motiver l'utilisateur à corriger le code et à réussir. "
        )
        
        response_motivation = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_motivation
        )
        motivational_text = response_motivation.text.strip()
        
    except Exception as e:
        print(f"[{COLOR_YELLOW}WARN:{COLOR_END}] Échec de la génération du texte motivant par Gemini: {e}. Utilisation du résumé standard.")
        motivational_text = f"Votre push a été annulé car l'analyse de code Gemini a détecté des problèmes critiques ou non conformes. {reason_summary}"


    # --- 2. ADAPTATION DU SALUT ET SUJET ---
    if user_name:
        greeting_text = f"Salut {user_name}, Maître du Code !"
    else:
        greeting_text = f"Salut Maître du Code !" 
    
    subject = f"🚨 PUSH BLOQUÉ : Revue de Code Critique par Gemini"
    
    # Préparation du contenu du rapport pour le HTML
    html_detailed_report = detailed_report.replace('\n', '<br>')
    
    # Styliser les tags
    html_detailed_report = re.sub(r'\[CRITICAL_ERROR\]', 
                                 '<span style="color: #FF6666; font-weight: bold;">[CRITICAL_ERROR]</span>', 
                                 html_detailed_report)
    html_detailed_report = re.sub(r'\[WARNING\]', 
                                 '<span style="color: #FFFF66; font-weight: bold;">[WARNING]</span>', 
                                 html_detailed_report)
    html_detailed_report = re.sub(r'--- Fichier: (.*) ---', 
                                 '<br><span style="color: #66CCFF; font-weight: bold; background: #333; padding: 2px 5px; display: inline-block;">Fichier: \\1</span><br>', 
                                 html_detailed_report)

    # Construction du corps HTML stylé
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Courier New', Courier, monospace; background-color: #282c34; color: white; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; background-color: #1e2127; border: 1px solid #61afef; padding: 20px; box-shadow: 0 0 10px rgba(97, 175, 239, 0.5); }}
        h1 {{ color: #e5c07b; border-bottom: 2px solid #56b6c2; padding-bottom: 5px; }}
        .report {{ white-space: pre-wrap; word-break: break-word; line-height: 1.5; }}
        .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #5c6370; color: white; font-size: 0.8em; }}
    </style>
</head>
<body>
    <div class="container">
        <span style="color: #98c379; font-size: 1.2em;">&gt;&gt;&gt; Initializing Code Review Protocol...</span>
        <h1>{greeting_text}</h1>

        <span style="color: #ff6666; font-weight: bold; margin-bottom: 15px; border-left: 3px solid #ff6666; padding-left: 10px; display: block;">
            🛑 PUSH ANNULÉ : Problèmes critiques détectés.
        </span>

        <span style="color: #61afef; font-weight: bold;">--- [ 💡 MOTIVATION & CONSEIL ] ---</span>
        <div style="margin-top: 10px; margin-bottom: 20px; padding: 10px; background-color: #2c313a; border: 1px dashed #e06c75;">
            <p style="color: white;">{motivational_text}</p>
        </div>

        <span style="color: #e5c07b; font-weight: bold;">--- [ 🛠️ DÉTAILS DU RAPPORT ] ---</span>
        <div class="report" style="margin-top: 10px; padding: 15px; background-color: #0d0e11; border: 1px solid #5c6370;">
            {html_detailed_report}
        </div>

        <div class="footer">
            <span style="color: #98c379;">&lt;-- Process finished with exit code 1.</span><br>
            Veuillez corriger ces problèmes et commiter/pusher à nouveau.<br>
            Merci,<br>
            L'équipe d'Analyse Gemini.
        </div>
    </div>
</body>
</html>
    """

    # Envoi du mail
    try:
        msg = MIMEText(html_body, 'html')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
        
        print(f"[{COLOR_GREEN}✉️ EMAIL{COLOR_END}] Rapport de blocage envoyé à {recipient_email}.")
    except Exception as e:
        print(f"{COLOR_RED}ERREUR EMAIL:{COLOR_END} Impossible d'envoyer l'e-mail à {recipient_email}: {e}", file=sys.stderr)


# --------------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------------

def main():
    
    # 1. LOGIQUE DE CHARGEMENT : CI/CD (GitHub Action) ou Local
    is_ci_cd = os.getenv('CI') == 'true'

    user_email = None
    user_name = None
    user_prefs = {}

    if is_ci_cd:
        # Mode CI/CD (GitHub Actions)
        # ... (Logique CI/CD inchangée) ...
        user_email = os.getenv("PUSHER_EMAIL") 
        user_name = os.getenv("PUSHER_NAME")   
        user_prefs = {'interest': os.getenv("PREF_INTEREST", 'la qualité du code')} 
        
        if not os.getenv("GEMINI_API_KEY"):
            print(f"\n{COLOR_RED}🛑 ERREUR CRITIQUE:{COLOR_END} La variable d'environnement GEMINI_API_KEY n'est pas définie dans la GitHub Action.", file=sys.stderr)
            sys.exit(1)
        
    else:
        # Mode Local (pre-push hook)
        # ... (Logique locale inchangée) ...
        load_dotenv() 
        user_prefs = load_user_prefs() 

        try:
            git_name_command = ["git", "config", "user.name"]
            user_name = subprocess.run(git_name_command, capture_output=True, text=True, check=False).stdout.strip()
            if not user_name: user_name = None
        except Exception:
            user_name = None
            
        try:
            git_email_command = ["git", "config", "user.email"]
            git_email = subprocess.run(git_email_command, capture_output=True, text=True, check=False).stdout.strip()
            if git_email:
                 user_email = git_email
        except Exception:
            pass 

        if not user_email:
             user_email = user_prefs.get('email', None)

        if not os.getenv("GEMINI_API_KEY"):
            print(f"\n{COLOR_RED}🛑 ERREUR CRITIQUE:{COLOR_END} La variable d'environnement GEMINI_API_KEY n'est pas définie dans votre .env.", file=sys.stderr)
            sys.exit(1)

    # 2. Initialisation, Détection de Langage et Analyse
    config = load_config()
    
    language, context = detect_project_language()
    
    dynamic_rules = LANGUAGE_RULES.get(language, LANGUAGE_RULES['General'])
    project_rules_override = config.get('rules_override', "Aucun override spécifié.")
    
    full_rules = f"Règles Spécifiques ({language}): {dynamic_rules}. Règle du Fichier Config: {project_rules_override}"
    
    # NOUVEAU: Récupération des commits si en mode pre-push
    # Lit STDIN si le script n'est pas en mode CI/CD et si une donnée est pipée (hook pre-push)
    refs_data = sys.stdin.read().strip() if not is_ci_cd and not sys.stdin.isatty() else None
    
    # MODIFIÉ: Appel de la fonction avec les références si disponibles
    files_to_analyze = get_files_and_patches(config, refs_data) 
    
    # ... (Le reste de la fonction est inchangé) ...

    print(f"{COLOR_BLUE}--- 🚀 Démarrage de l'analyse de code par Gemini ({'CI/CD' if is_ci_cd else 'pre-push'}) ---{COLOR_END}")
    print(f"{COLOR_BLUE}Contexte du Projet ({language}): {COLOR_END}{context}")
    
    cache = load_cache() 
    
    if not files_to_analyze:
        print(f"\n{COLOR_YELLOW}--- INFO HOOK : Aucun fichier pertinent trouvé. Poursuite. ---{COLOR_END}")
        sys.exit(0)
    
    has_critical_error = False
    full_report = "" 
    
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
        file_path = file_info['path'] 
        progress_bar.set_description(f"Analyse de {file_path.split('/')[-1]}")
        
        result, is_cached = analyze_code_with_gemini(file_info, config, context, cache, full_rules) 
        
        progress_bar.clear()
        
        # Logique de gestion du cache et de l'affichage console
        if is_cached:
            print(f"[{COLOR_BLUE}♻️ CACHE{COLOR_END}] {file_path} : Validation réutilisée.")
        elif "CODE_VALIDÉ" in result:
            print(f"[{COLOR_GREEN}✅{COLOR_END}] {file_path} : Code validé par Gemini.")
        else:
            full_report += f"\n--- Fichier: {file_path} ---\n{result}\n" 

            if "[CRITICAL_ERROR]" in result:
                print(f"[{COLOR_RED}🛑{COLOR_END}] {file_path} : {COLOR_RED}ERREURS CRITIQUES DÉTECTÉES !{COLOR_END}")
                has_critical_error = True
            elif "[WARNING]" in result:
                print(f"[{COLOR_YELLOW}⚠️{COLOR_END}] {file_path} : {COLOR_YELLOW}Avertissements !{COLOR_END}")
            else:
                is_strict = config['analyzer'].get('strict_untagged_output', False)
                if is_strict:
                    print(f"[{COLOR_RED}❌{COLOR_END}] {file_path} : {COLOR_RED}PROBLÈME DÉTECTÉ (Output non classifié - Mode strict) !{COLOR_END}")
                    has_critical_error = True 
                else:
                    print(f"[{COLOR_YELLOW}⚠️{COLOR_END}] {file_path} : {COLOR_YELLOW}Avertissements (non classifiés) !{COLOR_END}")

            print("-" * 50)
            print(result)
            print("-" * 50)
        
        progress_bar.display()

    progress_bar.close()
    
    save_cache(cache)

    # 3. Décision finale et Envoi d'E-mail
    if has_critical_error:
        reason_summary = "Des erreurs critiques ([CRITICAL_ERROR]) ont été trouvées, bloquant l'opération. Consultez les détails ci-dessous pour les corrections."
        print(f"\n{COLOR_RED}!!! 🛑 PUSH/COMMIT ANNULÉ : Des ERREURS CRITIQUES ont été détectées. !!!{COLOR_END}")
        
        if user_email:
            send_push_rejection_email(user_email, reason_summary, full_report, user_prefs, user_name)
        else:
            print(f"{COLOR_RED}ERREUR EMAIL:{COLOR_END} Impossible de déterminer l'adresse e-mail du destinataire.", file=sys.stderr)
            
        sys.exit(1) 
    else:
        print(f"\n{COLOR_GREEN}--- ✅ Analyse terminée. Code propre (ou seulement des avertissements). Poursuite. ---{COLOR_END}")
        sys.exit(0)

if __name__ == "__main__":
    main()