# scripts/get_top_clips.py
import requests
import os
import json
import sys
from datetime import datetime, timedelta, timezone

# Twitch API credentials from GitHub Secrets
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ ERREUR: TWITCH_CLIENT_ID ou TWITCH_CLIENT_SECRET non définis.")
    sys.exit(1)

TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_API_URL = "https://api.twitch.tv/helix/clips"

# --- PARAMÈTRES DE FILTRAGE ET DE SÉLECTION POUR LES SHORTS ---

# Ces paramètres de priorisation et de limite par streamer sont déplacés ou simplifiés
# car la logique de sélection finale est maintenant dans main.py qui va itérer sur cette liste complète.
# PRIORITIZE_BROADCASTERS_STRICTLY = True # Ce paramètre n'est plus pertinent car on ne cible qu'un streamer
# MAX_CLIPS_PER_BROADCASTER_IN_FINAL_SELECTION = 1 # Ce paramètre n'est plus pertinent

# La liste des IDs de jeux n'est plus nécessaire car nous ciblons un streamer spécifique.
# GAME_IDS = [
#     "509670",            # Just Chatting
#     "21779",             # League of Legends
#     # ... (et tous les autres IDs de jeux)
# ]

# Liste des IDs de streamers francophones populaires.
# Nous allons cibler uniquement Anyme023 ici.
# Si tu souhaites retrouver l'ID d'Anyme023, tu peux utiliser une API Twitch tool comme
# https://streams.rce.fr/tools/twitch-user-id
# Ou l'API Twitch directement (users endpoint).
TARGET_BROADCASTER_ID = "737048563"  # ID de Anyme023

# --- NOUVEAU PARAMÈTRE : Langue du clip ---
CLIP_LANGUAGE = "fr" # Code ISO 639-1 pour le français

# PARAMÈTRES POUR LA DURÉE CUMULÉE MINIMALE ET MAXIMALE DU SHORT FINAL
MIN_VIDEO_DURATION_SECONDS = 15     # Minimum 15 secondes pour un Short
MAX_VIDEO_DURATION_SECONDS = 180    # Maximum 180 secondes (3 minutes) pour un Short

# --- FIN PARAMÈTRES ---

def get_twitch_access_token():
    """Gets an application access token for Twitch API."""
    print("🔑 Récupération du jeton d'accès Twitch...")
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    try:
        response = requests.post(TWITCH_AUTH_URL, data=payload)
        response.raise_for_status()
        token_data = response.json()
        print("✅ Jeton d'accès Twitch récupéré.")
        return token_data["access_token"]
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la récupération du jeton d'accès Twitch : {e}")
        sys.exit(1)

def fetch_clips(access_token, params, source_type, source_id):
    """Helper function to fetch clips and handle errors."""
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    try:
        response = requests.get(TWITCH_API_URL, headers=headers, params=params)
        response.raise_for_status()
        clips_data = response.json()
        
        if not clips_data.get("data"):
            print(f"  ⚠️ Aucune donnée de clip trouvée pour {source_type} {source_id} dans la période spécifiée.")
            return []

        collected_clips = []
        for clip in clips_data.get("data", []):
            collected_clips.append({
                "id": clip.get("id"),
                "url": clip.get("url"),
                "embed_url": clip.get("embed_url"),
                "thumbnail_url": clip.get("thumbnail_url"),
                "title": clip.get("title"),
                # CORRECTION ICI: Utilise "view_count" au lieu de "viewer_count"
                "viewer_count": clip.get("view_count", 0),  # Clé correcte de l'API Twitch
                "broadcaster_id": clip.get("broadcaster_id"),
                "broadcaster_name": clip.get("broadcaster_name"),
                "game_name": clip.get("game_name"),
                "created_at": clip.get("created_at"),
                "duration": float(clip.get("duration", 0.0)),
                "language": clip.get("language")
            })
        return collected_clips
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la récupération des clips Twitch pour {source_type} {source_id} : {e}")
        if response.content:
            print(f"    Contenu de la réponse API Twitch: {response.content.decode()}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Erreur de décodage JSON pour {source_type} {source_id}: {e}")
        if response.content:
            print(f"    Contenu brut de la réponse: {response.content.decode()}")
        return []

def get_eligible_short_clips(access_token, num_clips_per_source=50, days_ago=1, already_published_clip_ids=None):
    """
    Récupère les clips populaires du streamer Anyme023,
    filtre ceux déjà publiés et ceux qui ne respectent pas les contraintes de durée/langue.
    Retourne une liste de clips éligibles, triés par popularité (vues).
    """
    if already_published_clip_ids is None:
        already_published_clip_ids = []

    print(f"📊 Recherche de clips éligibles ({MIN_VIDEO_DURATION_SECONDS}-{MAX_VIDEO_DURATION_SECONDS}s) pour les dernières {days_ago} jour(s) pour Anyme023...")
    print(f"Clips déjà publiés aujourd'hui (transmis) : {len(already_published_clip_ids)} IDs.")
            
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_ago)
            
    # Utilise un set pour une recherche rapide et pour éviter les doublons lors de la collecte
    seen_clip_ids = set(already_published_clip_ids) 
    all_potential_clips = []

    # --- Phase de collecte : Uniquement les clips du streamer cible ---
    print("\n--- Collecte des clips du streamer Anyme023 ---")
    params = {
        "first": num_clips_per_source,
        "started_at": start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "ended_at": end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "sort": "views",
        "broadcaster_id": TARGET_BROADCASTER_ID, # Utilise le nouvel ID cible unique
        "language": CLIP_LANGUAGE
    }
    clips = fetch_clips(access_token, params, "broadcaster_id", TARGET_BROADCASTER_ID)
    for clip in clips:
        # Filtrer par langue et durée dès la collecte pour optimiser
        if (clip["id"] not in seen_clip_ids and 
            clip.get('language') == CLIP_LANGUAGE and
            MIN_VIDEO_DURATION_SECONDS <= clip.get('duration', 0.0) <= MAX_VIDEO_DURATION_SECONDS):
            all_potential_clips.append(clip)
            seen_clip_ids.add(clip["id"]) # Ajoute à 'seen' pour éviter les doublons globaux
    print(f"✅ Collecté {len(all_potential_clips)} clips uniques éligibles pour Anyme023.")

    # Il n'y a plus de collecte par jeu, donc nous n'avons qu'une seule source de clips.

    # Trier tous les clips éligibles par vues (plus populaire en premier)
    all_potential_clips.sort(key=lambda x: x.get('viewer_count', 0), reverse=True)

    if not all_potential_clips:
        print(f"⚠️ Aucun clip éligible trouvé après collecte et filtrage (durée entre {MIN_VIDEO_DURATION_SECONDS} et {MAX_VIDEO_DURATION_SECONDS}s, non publié) pour Anyme023.")
        return [] # Retourne une liste vide
    else:
        print(f"Found {len(all_potential_clips)} clips éligibles au total pour Anyme023, triés par vues.")
    return all_potential_clips

# Le bloc if __name__ == "__main__": peut être laissé tel quel ou simplifié pour un test rapide
if __name__ == "__main__":
    token = get_twitch_access_token()
    if token:
        # Simule l'historique de publication pour le test
        published_clips_log_path = os.path.join("data", "published_shorts_history.json")
        current_published_ids = []
        if os.path.exists(published_clips_log_path):
            try:
                with open(published_clips_log_path, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
                    today_str = datetime.now(timezone.utc).date().isoformat()
                    if today_str in history_data:
                        current_published_ids = [item["twitch_clip_id"] for item in history_data[today_str]]
            except json.JSONDecodeError:
                print("⚠️ Fichier d'historique des publications corrompu ou vide. Utilisation d'un historique vide.")
            except Exception as e:
                print(f"❌ Erreur lors du chargement de l'historique simulé : {e}")

        eligible_clips_list = get_eligible_short_clips(
            access_token=token,
            num_clips_per_source=50,
            days_ago=1,
            already_published_clip_ids=current_published_ids
        )

        if eligible_clips_list:
            print(f"\n✅ {len(eligible_clips_list)} clip(s) éligible(s) trouvé(s) pour les Shorts.")
            print("Premier clip suggéré :")
            selected_clip = eligible_clips_list[0]
            print(f"  Titre: {selected_clip.get('title', 'N/A')}")
            print(f"  Streamer: {selected_clip.get('broadcaster_name', 'N/A')}")
            print(f"  Vues: {selected_clip.get('viewer_count', 0)}")
            print(f"  Durée: {selected_clip.get('duration', 'N/A')}s")
            print(f"  URL: {selected_clip.get('url', 'N/A')}")
        else:
            print("\n❌ Aucun clip approprié n'a pu être trouvé pour le Short cette fois.")