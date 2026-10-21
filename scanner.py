import os
import sqlite3
import pytesseract
import requests
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image, ImageGrab

# 🔑 METTEZ VOTRE CLÉ API RAWG ICI (https://rawg.io)
API_KEY_RAWG = "VOTRE_CLE_API_RAWG" 

# ========================================================
# 📦 CONFIGURATION DE LA SAUVEGARDE SUR L'APPAREIL LOCALE
# ========================================================
def initialiser_base_locale():
    # Détecte automatiquement le dossier "Documents" de l'appareil (Windows ou Mac)
    dossier_documents = os.path.join(os.path.expanduser('~'), 'Documents')
    
    # Crée un sous-dossier dédié pour votre outil s'il n'existe pas
    dossier_app = os.path.join(dossier_documents, 'ScannerJeuxVideo')
    if not os.path.exists(dossier_app):
        os.makedirs(dossier_app)
        
    # Chemin final de la base de données sur la machine
    chemin_bdd = os.path.join(dossier_app, 'catalogue_jeux.db')
    print(f"💾 Sauvegarde locale activée à l'emplacement : {chemin_bdd}")
    
    conn = sqlite3.connect(chemin_bdd)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jeux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prix REAL NOT NULL,
            code_barres TEXT UNIQUE,
            image_url TEXT,
            console_principale TEXT
        )
    ''')
    conn.commit()
    return conn, chemin_bdd

# ========================================================
# 🤖 RECHERCHE AUTOMATIQUE DE CATÉGORIE ET JAQUETTE
# ========================================================
def chercher_infos_jeu_internet(nom_jeu):
    if API_KEY_RAWG == "VOTRE_CLE_API_RAWG" or not nom_jeu:
        return None, "Inconnu"
    try:
        url = f"https://rawg.io{API_KEY_RAWG}&search={nom_jeu}&page_size=1"
        reponse = requests.get(url).json()
        if reponse.get('results'):
            premier_jeu = reponse['results'][0]
            image_url = premier_jeu.get('background_image')
            platforms = [p['platform']['name'] for p in premier_jeu.get('platforms', [])]
            
            # Rangement intelligent par catégorie de console
            console_preferee = "Autre"
            for p in platforms:
                p_low = p.lower()
                if "playstation 5" in p_low or "ps5" in p_low: console_preferee = "PS5"; break
                elif "playstation 4" in p_low or "ps4" in p_low: console_preferee = "PS4"; break
                elif "playstation 3" in p_low or "ps3" in p_low: console_preferee = "PS3"; break
                elif "playstation 2" in p_low or "ps2" in p_low: console_preferee = "PS2"; break
                elif "nintendo switch" in p_low: console_preferee = "Switch"; break
                elif "wii u" in p_low: console_preferee = "Wii U"; break
                elif "wii" in p_low: console_preferee = "Wii"; break
                elif "nintendo 3ds" in p_low: console_preferee = "3DS"; break
                elif "nintendo ds" in p_low: console_preferee = "DS"; break
                elif "playstation 1" in p_low or "ps1" in p_low: console_preferee = "PS1"; break
            
            if console_preferee == "Autre" and platforms:
                console_preferee = platforms[0]
                
            return image_url, console_preferee
    except Exception:
        pass
    return None, "Inconnu"

# ========================================================
# 🏁 APPLICATION PRINCIPALE
# ========================================================
conn, chemin_stockage = initialiser_base_locale()
cursor = conn.cursor()

while True:
    print("\n" + "="*40)
    print("🎮 SCANNER DE JEUX - MENU PRINCIPAL")
    print("="*40)
    print("1. 📸 SCANNER L'ÉCRAN (Code-barres ou Texte)")
    print("2. ➕ Ajouter / Modifier un tarif manuellement")
    print("3. 📁 Voir ma bibliothèque par console")
    print("4. 💾 Afficher l'emplacement de ma sauvegarde")
    print("5. ❌ Quitter")
    
    choix = input("\nFaites votre choix (1-5) : ").strip()
    
    if choix == "1":
        print("\n[Analyse de l'écran en cours... Assurez-vous que le titre ou le code-barres est visible]")
        # Capture de l'écran de la machine
        img_ecran = ImageGrab.grab()
        
        # A. Vérification de code-barres
        image_cv = cv2.cvtColor(np.array(img_ecran), cv2.COLOR_RGB2BGR)
        codes_detectes = decode(image_cv)
        
        resultat = None
        code_chiffres = None
        texte_scanne = ""
        
        if codes_detectes:
            code_chiffres = codes_detectes[0].data.decode('utf-8')
            print(f"🔍 Code-barres détecté : {code_chiffres}")
            cursor.execute("SELECT nom, prix, console_principale FROM jeux WHERE code_barres = ?", (code_chiffres,))
            resultat = cursor.fetchone()
        else:
            # B. Analyse par texte (OCR) si aucun code-barres n'est visible
            texte_scanne = pytesseract.image_to_string(img_ecran).strip()
            if texte_scanne:
                print(f"🔍 Lettres lues à l'écran : '{texte_scanne}'")
                cursor.execute("SELECT nom, prix, console_principale FROM jeux WHERE LOWER(nom) LIKE ?", (f"%{texte_scanne.lower()}%",))
                resultat = cursor.fetchone()
        
        # C. Affichage du prix
        if resultat:
            nom, prix, console = resultat
            print(f"\n✅ JEU IDENTIFIÉ !")
            print(f"• Nom : {nom}")
            print(f"• Catégorie : [{console}]")
            print(f"• Votre Prix : {prix} €")
        else:
            print("\n⚠️ Ce jeu ou code-barres n'est pas répertorié dans vos tarifs locaux.")
            reponse = input("Voulez-vous l'ajouter maintenant ? (o/n) : ").lower().strip()
            if reponse == 'o':
                nom_rapide = input(f"Nom du jeu (par défaut : '{texte_scanne}') : ") or texte_scanne
                if nom_rapide:
                    prix_rapide = float(input("Entrez votre prix de vente (€) : "))
                    img_url, console_auto = chercher_infos_jeu_internet(nom_rapide)
                    cursor.execute('''
                        INSERT OR REPLACE INTO jeux (nom, prix, code_barres, image_url, console_principale) 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (nom_rapide, prix_rapide, code_chiffres, img_url, console_auto))
                    conn.commit()
                    print(f"🎉 Enregistré dans la catégorie : {console_auto}")

    elif choix == "2":
        nom_jeu = input("\nNom du jeu (ex: Super Mario Odyssey) : ").strip()
        if nom_jeu:
            prix_jeu = float(input("Votre prix personnalisé (€) : "))
            cb_jeu = input("Code-barres (Optionnel - tapez-le ou laissez vide) : ").strip()
            
            print("⏳ Recherche de la catégorie et de la jaquette sur internet...")
            img_url, console_auto = chercher_infos_jeu_internet(nom_jeu)
            
            cursor.execute('''
                INSERT OR REPLACE INTO jeux (nom, prix, code_barres, image_url, console_principale) 
                VALUES (?, ?, ?, ?, ?)
            ''', (nom_jeu, prix_jeu, cb_jeu if cb_jeu else None, img_url, console_auto))
            conn.commit()
            print(f"🎉 Mis à jour ! Classé dans la catégorie : {console_auto}")

    elif choix == "3":
        cursor.execute("SELECT DISTINCT console_principale FROM jeux ORDER BY console_principale ASC")
        categories = cursor.fetchall()
        
        if categories:
            for (console,) in categories:
                print(f"\n📁 CONSOLE : {console}")
                print("-" * 25)
                cursor.execute("SELECT nom, prix, code_barres FROM jeux WHERE console_principale = ? ORDER BY nom ASC", (console,))
                for nom, prix, cb in cursor.fetchall():
                    infos_cb = f" (CB: {cb})" if cb else ""
                    print(f"  └─ {nom:<30} | Tarif : {prix} €{infos_cb}")
        else:
            print("\n📋 Votre bibliothèque locale est vide.")

    elif choix == "4":
        print(f"\nℹ️ Vos données sont en sécurité ici : {chemin_stockage}")

    elif choix == "5":
        print("\n👋 Fermeture de l'application. À bientôt !")
        break

conn.close()
