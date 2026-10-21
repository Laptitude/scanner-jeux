import os
import sqlite3
import pytesseract
import requests
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image
import streamlit as st

# Configuration de la page web pour mobile
st.set_page_config(page_title="Mon Scanner de Jeux", page_icon="🎮", layout="centered")

# Clé API RAWG (https://rawg.io)
API_KEY_RAWG = "VOTRE_CLE_API_RAWG" 

# ========================================================
# 📦 CONFIGURATION DE LA SAUVEGARDE PERMANENTE (ANTI-EFFACEMENT)
# ========================================================
# Hugging Face propose un dossier sécurisé "/data" qui ne s'efface jamais
if os.path.exists("/data"):
    chemin_bdd = "/data/catalogue_jeux.db"
else:
    chemin_bdd = "catalogue_jeux.db" # Version de secours locale

conn = sqlite3.connect(chemin_bdd, check_same_thread=False)
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

# ========================================================
# 🤖 RECHERCHE AUTOMATIQUE (RAWG)
# ========================================================
def chercher_infos_jeu_internet(nom_jeu):
    if API_KEY_RAWG == "VOTRE_CLE_API_RAWG" or not nom_jeu:
        return None, "Inconnu"
    try:
        url = f"https://rawg.io{API_KEY_RAWG}&search={nom_jeu}&page_size=1"
        reponse = requests.get(url).json()
        if reponse.get('results'):
            premier_jeu = reponse['results']
            image_url = premier_jeu.get('background_image')
            platforms = [p['platform']['name'] for p in premier_jeu.get('platforms', [])]
            
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
            return image_url, console_preferee
    except Exception: pass
    return None, "Inconnu"

# ========================================================
# 🏁 INTERFACE WEB NAVIGATION
# ========================================================
choix_menu = st.sidebar.radio("Navigation", ["🔍 Scanner un Jeu", "⚙️ Bibliothèque & Tarifs"])

if choix_menu == "🔍 Scanner un Jeu":
    st.title("🎮 Scanner de Jeux")
    source = st.radio("Source de la photo :", ["📸 Caméra du Téléphone", "🖼️ Galerie"], horizontal=True)
    image_recue = st.camera_input("Prendre une photo") if source == "📸 Caméra du Téléphone" else st.file_uploader("Choisir une image", type=["jpg", "png", "jpeg"])

    if image_recue:
        img_pil = Image.open(image_recue)
        with st.spinner("Analyse de l'image..."):
            image_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            codes_detectes = decode(image_cv)
            resultat = None
            code_chiffres = None
            texte_scanne = ""
            
            if codes_detectes:
                code_chiffres = codes_detectes.data.decode('utf-8')
                st.info(f" Code-barres trouvé : `{code_chiffres}`")
                cursor.execute("SELECT nom, prix, image_url, console_principale FROM jeux WHERE code_barres = ?", (code_chiffres,))
                resultat = cursor.fetchone()
            else:
                texte_scanne = pytesseract.image_to_string(img_pil).strip()
                if texte_scanne:
                    st.subheader(f"Texte détecté : *{texte_scanne}*")
                    cursor.execute("SELECT nom, prix, image_url, console_principale FROM jeux WHERE LOWER(nom) LIKE ?", (f"%{texte_scanne.lower()}%",))
                    resultat = cursor.fetchone()
            
            if resultat:
                nom, prix, url, cat_console = resultat
                st.success(f"### ✅ {nom}")
                st.caption(f"📁 Catégorie : **{cat_console}**")
                if url: st.image(url, use_container_width=True)
                st.metric(label="Votre tarif", value=f"{prix} €")
            else:
                st.warning("⚠️ Ce jeu n'est pas encore répertorié.")
                with st.expander("➕ L'ajouter à votre bibliothèque web"):
                    nouveau_nom = st.text_input("Nom du jeu", value=texte_scanne)
                    nouveau_prix = st.number_input("Votre prix (€)", min_value=0.0, step=1.0)
                    if st.button("Enregistrer le tarif"):
                        img_url, console_auto = chercher_infos_jeu_internet(nouveau_nom)
                        cursor.execute("INSERT OR REPLACE INTO jeux (nom, prix, code_barres, image_url, console_principale) VALUES (?, ?, ?, ?, ?)",
                                       (nouveau_nom, nouveau_prix, code_chiffres, img_url, console_auto))
                        conn.commit()
                        st.success(f"Ajouté dans {console_auto} !")
                        st.rerun()

elif choix_menu == "⚙️ Bibliothèque & Tarifs":
    st.title("⚙️ Votre Bibliothèque Globale")
    # Formulaire d'ajout manuel classique
    with st.expander("➕ Ajouter un jeu manuellement"):
        with st.form("ajout_manuel", clear_on_submit=True):
            nom_jeu = st.text_input("Nom du jeu vidéo")
            prix_jeu = st.number_input("Prix de vente (€)", min_value=0.0, step=0.5)
            cb_jeu = st.text_input("Code-barres (Optionnel)")
            if st.form_submit_button("Enregistrer"):
                if nom_jeu.strip():
                    img_url, console_auto = chercher_infos_jeu_internet(nom_jeu.strip())
                    cursor.execute("INSERT OR REPLACE INTO jeux (nom, prix, code_barres, image_url, console_principale) VALUES (?, ?, ?, ?, ?)",
                                   (nom_jeu.strip(), prix_jeu, cb_jeu.strip() if cb_jeu else None, img_url, console_auto))
                    conn.commit()
                    st.success(f"Classé automatiquement dans : {console_auto}")

    # Affichage trié par console
    cursor.execute("SELECT DISTINCT console_principale FROM jeux ORDER BY console_principale ASC")
    categories = cursor.fetchall()
    if categories:
        for (console,) in categories:
            with st.expander(f"📁 Jeux {console}", expanded=False):
                cursor.execute("SELECT nom, prix, code_barres, image_url FROM jeux WHERE console_principale = ? ORDER BY nom ASC", (console,))
                for nom, prix, cb, url in cursor.fetchall():
                    col1, col2 = st.columns()
                    with col1:
                        st.write(f"**{nom}**")
                        st.caption(f"Tarif : {prix} € {f'| CB : {cb}' if cb else ''}")
                    with col2:
                        if url: st.image(url, width=65)
                    st.divider()
    else:
        st.info("Votre bibliothèque est vide.")
