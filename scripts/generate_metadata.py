# scripts/generate_metadata.py
import json
from datetime import datetime
import locale
import os

def generate_youtube_metadata(clip_data):
    """
    Génère un dictionnaire de métadonnées pour un Short YouTube.

    Args:
        clip_data (dict): Le dictionnaire contenant les informations du clip sélectionné.

    Returns:
        dict: Un dictionnaire contenant 'title', 'description', et 'tags' (liste de strings).
    """
    print("📝 Génération des métadonnées vidéo (titre, description, tags)...")

    # Assurez-vous que broadcaster_name et game_name ne sont jamais None
    # Utilisez .get() avec une valeur par défaut, puis vérifiez si la valeur obtenue est None
    broadcaster_name = clip_data.get("broadcaster_name", "Un streamer")
    if broadcaster_name is None: # Nouvelle vérification si la valeur est None
        broadcaster_name = "Un streamer"

    game_name = clip_data.get("game_name", "Gaming")
    if game_name is None: # Nouvelle vérification si la valeur est None
        game_name = "Gaming"

    clip_title_raw = clip_data.get("title", "Un moment épique")
    # Nettoyer le titre du clip pour éviter des caractères non souhaités dans le titre YouTube
    # Permet seulement lettres, chiffres, espaces, et quelques signes de ponctuation courants
    clip_title_clean = ''.join(char for char in clip_title_raw if char.isalnum() or char.isspace() or char in "'-_!?.")
    clip_title_clean = clip_title_clean.strip() # Supprime les espaces en début/fin

    # Tente de définir la locale pour une date en français, sinon utilise par défaut
    try:
        # Essai avec des locales spécifiques pour Linux et macOS
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR')
        except locale.Error:
            print("⚠️ Impossible de définir la locale française pour la date. La date sera en anglais.")
            pass # Fallback to default locale if French is not available

    # Formatage de la date du jour
    # Utilisez %d %B %Y pour jour, nom du mois complet, année.
    # Assurez-vous que la locale est appliquée pour le nom du mois.
    today_date = datetime.now().strftime('%d %B %Y')

    # Titre du Short
    title = f"{clip_title_clean} par @{broadcaster_name} | Anyme Rediff Twitch - {today_date}"
    # S'assurer que le titre ne dépasse pas 100 caractères pour YouTube
    if len(title) > 100:
        # Tronque au lieu de couper brutalement pour éviter un titre trop long
        title = title[:97].strip() + "..." 

    # Description du Short
    # Correction ici: Appliquer .replace() sur les variables locales qui sont garanties non-None
    clean_broadcaster_name_for_url = broadcaster_name.replace(' ', '')
    # La ligne suivante était la cause de l'erreur si game_name était None
    clean_game_name_for_hashtag = game_name.replace(' ', '')


    description = f"""Les meilleurs moments de Twitch par {broadcaster_name} !
Ce Short présente le clip le plus vu du jour : "{clip_title_raw}"

N'oubliez pas de vous abonner pour plus de Shorts Twitch chaque jour !
Chaîne de {broadcaster_name} : https://www.twitch.tv/{clean_broadcaster_name_for_url}
Lien direct vers le clip : {clip_data.get('url', 'N/A')}

#Twitch #Shorts #ClipsTwitch #Gaming #{clean_broadcaster_name_for_url} #{clean_game_name_for_hashtag}
"""
    # YouTube limite les descriptions à 5000 caractères, ce qui est largement suffisant ici.

    # Tags du Short
    # NOUVELLE LOGIQUE POUR LES TAGS : Assurez-vous qu'ils sont une LISTE de chaînes
    raw_tags = [
        "Twitch", "Shorts", "ClipsTwitch", "MeilleursMomentsTwitch",
        "Gaming", "Gameplay", "Drôle", "Épique", "Highlight", 
        broadcaster_name, game_name,
        "TwitchFr", "ShortsGaming"
    ]
    
    # Nettoyage et normalisation des tags:
    # 1. Convertir en minuscules pour la cohérence
    # 2. Remplacer les espaces par des tirets (convention habituelle pour les tags à plusieurs mots)
    # 3. Supprimer les tags vides ou redondants
    # 4. Utiliser un set pour supprimer les doublons
    tags = list(set([
        tag.strip().lower().replace(' ', '-') for tag in raw_tags if tag.strip()
    ]))

    # Ajout de tags spécifiques à partir du titre du clip, si pertinent (facultatif)
    # Par exemple, si le titre est "Mon kill épique", on pourrait ajouter "MonKillEpique"
    # Ici, nous allons juste prendre les mots clés du titre nettoyé
    for word in clip_title_clean.split():
        cleaned_word = word.strip().lower()
        if len(cleaned_word) > 2 and cleaned_word not in tags: # Évite les mots trop courts et les doublons
            tags.append(cleaned_word)

    # YouTube API attend une liste de chaînes pour les tags, pas une chaîne unique
    metadata = {
        "title": title,
        "description": description,
        "tags": tags, # IMPORTANT : C'est une LISTE de strings ici
        "categoryId": "20", # Catégorie "Gaming" pour YouTube
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False, # Important pour les Shorts non destinés aux enfants
        "embeddable": True,
        "license": "youtube", # Standard YouTube License
    }

    print(f"✅ Métadonnées générées.")
    print(f"  Titre: {metadata['title']}")
    # Afficher les tags correctement formatés pour le débogage
    print(f"  Tags: {', '.join(metadata['tags'])}") 
    
    return metadata

if __name__ == "__main__":
    # Exemple d'utilisation (pour les tests locaux)
    print("Ce script est conçu pour être exécuté via main.py.")
    print("Pour un test direct, fournissez un dictionnaire de données de clip.")
    test_clip_data = {
        "broadcaster_name": "ToneEUW",
        "title": "Je l'ai eu !!!!",
        "game_name": None, # Teste le cas où game_name est explicitement None
        "url": "https://www.twitch.tv/toneeuw/clip/CloudySpotlessHippoThisIsSparta-o7pRPUkEfKHBA5KC"
    }
    metadata = generate_youtube_metadata(test_clip_data)
    print("\nMétadonnées générées pour test :")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))