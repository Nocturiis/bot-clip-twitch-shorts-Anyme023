# main.py

import sys
import os
import json
from datetime import datetime, date

# Ajouter le répertoire 'scripts' au PYTHONPATH pour importer les modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

import get_top_clips
import download_clip
import process_video
import generate_metadata
import upload_youtube


# --- Chemins et configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

PUBLISHED_HISTORY_FILE = os.path.join(DATA_DIR, 'published_shorts_history.json')
# Fichiers temporaires pour le clip
RAW_CLIP_PATH = os.path.join(DATA_DIR, 'temp_raw_clip.mp4')
PROCESSED_CLIP_PATH = os.path.join(DATA_DIR, 'temp_processed_short.mp4')

# --- CONSTANTE DE CONFIGURATION CLÉ ---
# Nombre de clips que le script essaiera de publier lors d'UNE SEULE EXÉCUTION du workflow.
# Si votre GitHub Action est configurée pour s'exécuter 3 fois par jour, laissez cette valeur à 1.
# Si votre GitHub Action s'exécute 1 fois par jour et que vous voulez 3 clips, changez cette valeur à 3.
NUMBER_OF_CLIPS_TO_ATTEMPT_TO_PUBLISH = 3
# ----------------------------------------

# --- Fonctions utilitaires pour l'historique ---
def load_published_history():
    """Charge l'historique des clips publiés."""
    if not os.path.exists(PUBLISHED_HISTORY_FILE):
        return {}
    try:
        with open(PUBLISHED_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Fichier d'historique des publications corrompu. Création d'un nouveau.")
        return {}
    except Exception as e:
        print(f"❌ Erreur inattendue lors du chargement de l'historique : {e}")
        return {}

def save_published_history(history_data):
    """Sauvegarde l'historique des clips publiés."""
    try:
        with open(PUBLISHED_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erreur inattendue lors de la sauvegarde de l'historique : {e}")


def get_today_published_ids(history_data):
    """Retourne les IDs des clips publiés aujourd'hui."""
    today_str = date.today().isoformat()
    # history_data est un dict { "YYYY-MM-DD": [ {clip_id: ..., youtube_id: ...}, ... ] }
    # Retourne seulement les 'twitch_clip_id' pour la date d'aujourd'hui
    return [item["twitch_clip_id"] for item in history_data.get(today_str, [])]

def add_to_history(history_data, clip_id, youtube_id):
    """Ajoute un clip à l'historique pour la date d'aujourd'hui."""
    today_str = date.today().isoformat()
    if today_str not in history_data:
        history_data[today_str] = []
        
    # Vérifier si l'ID Twitch est déjà dans la liste d'aujourd'hui pour éviter les doublons accidentels
    # (bien que la logique de sélection devrait déjà filtrer cela)
    if not any(item["twitch_clip_id"] == clip_id for item in history_data[today_str]):
        history_data[today_str].append({
            "twitch_clip_id": clip_id, 
            "youtube_short_id": youtube_id, 
            "timestamp": datetime.now().isoformat()
        })
    
    # OPTIONNEL: Nettoyer l'historique des anciennes entrées (ex: plus de 7 jours)
    # C'est une bonne pratique pour éviter que le fichier ne devienne trop gros.
    # Décommentez le bloc ci-dessous si vous voulez cette fonctionnalité.
    # old_dates = []
    # for d in history_data:
    #     try:
    #         if (datetime.now().date() - datetime.fromisoformat(d).date()).days > 7:
    #             old_dates.append(d)
    #     except ValueError: # Gérer les dates mal formatées si nécessaire
    #         print(f"⚠️ Date mal formatée dans l'historique : {d}. Ignorée.")
    # for d in old_dates:
    #     del history_data[d]
    # if old_dates:
    #     print(f"Historique nettoyé. {len(old_dates)} anciennes entrées supprimées.")


def main():
    print("🚀 Début du workflow de publication de Short YouTube...")

    # 1. Charger l'historique des clips publiés
    history = load_published_history()
    today_published_ids = get_today_published_ids(history)
    print(f"Clips déjà publiés aujourd'hui (selon l'historique) : {len(today_published_ids)} IDs.")

    # Garder une trace des clips que nous avons ATTEMPTÉ de publier DANS CETTE EXÉCUTION
    # pour éviter de retenter le même si la première tentative échoue et la boucle continue.
    clips_attempted_in_this_run = []

    # 2. Récupérer le jeton d'accès Twitch
    twitch_token = get_top_clips.get_twitch_access_token()
    if not twitch_token:
        print("❌ Impossible d'obtenir le jeton d'accès Twitch. Fin du script.")
        return # Quitter la fonction main sans sys.exit(1) pour éviter un échec "fatal" du workflow.

    # 3. Récupérer TOUS les clips éligibles et triés
    # On passe les IDs déjà publiés AUJOURD'HUI pour qu'ils soient filtrés dès la source.
    eligible_clips_list = get_top_clips.get_eligible_short_clips(
        access_token=twitch_token,
        num_clips_per_source=50, # Augmenter pour avoir plus de candidats
        days_ago=1, # Chercher les clips du dernier jour
        already_published_clip_ids=today_published_ids # Passer l'historique des clips publiés CE JOUR
    )

    if not eligible_clips_list:
        print("🤷‍♂️ Aucun nouveau clip adapté trouvé pour la publication aujourd'hui. Fin du script.")
        # Sortie normale si aucun clip à traiter
        return 

    # --- Boucle de traitement et d'upload pour le nombre de clips souhaité ---
    clips_published_count = 0
    for selected_clip in eligible_clips_list:
        if clips_published_count >= NUMBER_OF_CLIPS_TO_ATTEMPT_TO_PUBLISH:
            print(f"✅ Objectif de {NUMBER_OF_CLIPS_TO_ATTEMPT_TO_PUBLISH} clip(s) atteint pour cette exécution.")
            break # Sortir de la boucle si on a publié le nombre désiré

        # Vérifier si ce clip a déjà été tenté OU PUBLIÉ (par une exécution précédente) dans cette journée
        if selected_clip['id'] in clips_attempted_in_this_run or selected_clip['id'] in today_published_ids:
            print(f"ℹ️ Clip '{selected_clip['id']}' déjà tenté dans cette exécution ou déjà publié aujourd'hui. Passage au suivant.")
            continue # Passe au prochain clip éligible

        # Marquer le clip comme tenté pour cette exécution pour éviter les re-tentatives immédiates
        clips_attempted_in_this_run.append(selected_clip['id'])
        print(f"\n✨ Tentative de publication du clip : '{selected_clip['title']}' par '{selected_clip['broadcaster_name']}' (ID: {selected_clip['id']})...")

        # 4. Télécharger le clip
        downloaded_file = download_clip.download_twitch_clip(selected_clip['url'], RAW_CLIP_PATH)
        if not downloaded_file:
            print(f"❌ Échec du téléchargement du clip '{selected_clip['id']}'. Passage au suivant.")
            # Nettoyage spécifique si le téléchargement a laissé des traces
            if os.path.exists(RAW_CLIP_PATH): os.remove(RAW_CLIP_PATH)
            continue # Passe au prochain clip éligible

        # 5. Traiter/couper la vidéo
        print("🎬 Traitement de la vidéo pour le format Short (découpage si nécessaire)...")
        current_processed_file = PROCESSED_CLIP_PATH # Assurez-vous d'écraser le précédent pour l'artefact final

        processed_file_path_returned = process_video.trim_video_for_short(
            input_path=downloaded_file,
            output_path=current_processed_file,
            max_duration_seconds=get_top_clips.MAX_VIDEO_DURATION_SECONDS,
            clip_data=selected_clip,
            enable_webcam_crop=False
        )
        
        # Vérifications après traitement
        if not processed_file_path_returned or not os.path.exists(processed_file_path_returned) or os.path.getsize(processed_file_path_returned) == 0:
            print(f"❌ Échec du traitement vidéo pour le clip '{selected_clip['id']}'. Le fichier traité est manquant ou vide.")
            print("Tentative d'utiliser le fichier brut pour l'upload si possible (peut être trop long).")
            final_video_for_upload = downloaded_file # Utilise le fichier brut comme fallback
            if not os.path.exists(final_video_for_upload) or os.path.getsize(final_video_for_upload) == 0:
                print(f"❌ Le fichier brut pour le clip '{selected_clip['id']}' est aussi vide ou introuvable. Impossible de continuer pour ce clip.")
                # Nettoyage des temporaires avant de passer au suivant
                if os.path.exists(RAW_CLIP_PATH): os.remove(RAW_CLIP_PATH)
                if os.path.exists(current_processed_file): os.remove(current_processed_file) 
                continue # Passe au prochain clip éligible
            else:
                print(f"Utilisation du fichier brut pour l'upload du clip '{selected_clip['id']}'.")
        else:
            print(f"✅ Fichier traité trouvé et non vide : {processed_file_path_returned} (taille : {os.path.getsize(processed_file_path_returned)} octets).")
            final_video_for_upload = processed_file_path_returned # Utilise le fichier traité

        # 6. Générer les métadonnées YouTube
        youtube_metadata = generate_metadata.generate_youtube_metadata(selected_clip)
        print("\n--- Informations sur le Short (pour débogage) ---")
        print(f"Titre: {youtube_metadata.get('title')}")
        print(f"Description: {youtube_metadata.get('description')}")
        print(f"Tags: {', '.join(youtube_metadata.get('tags', []))}")
        print(f"Chemin de la vidéo finale pour upload: {final_video_for_upload}")
        print("-------------------------------------------------\n")

        # 7. Authentifier et Uploader sur YouTube
        youtube_service = None
        try:
            youtube_service = upload_youtube.get_authenticated_service()
        except Exception as e:
            print(f"❌ Erreur lors de l'authentification YouTube : {e}")
            print("ℹ️ L'upload YouTube pour ce clip sera ignoré. Le script continuera pour le prochain clip/l'artefact.")

        youtube_video_id = None
        if youtube_service:
            print("📤 Démarrage de l'upload YouTube...")
            try:
                youtube_video_id = upload_youtube.upload_youtube_short(youtube_service, final_video_for_upload, youtube_metadata)
                
                if youtube_video_id:
                    print(f"🎉 Short YouTube publié avec succès ! ID: {youtube_video_id}")
                    # 8. Mettre à jour l'historique des publications seulement si l'upload YouTube réussit
                    try:
                        add_to_history(history, selected_clip['id'], youtube_video_id)
                        save_published_history(history)
                        # Recharger today_published_ids pour que la prochaine itération de la boucle
                        # ou une exécution future dans la même journée la voie comme publiée.
                        today_published_ids = get_today_published_ids(history) 
                        print(f"✅ Clip '{selected_clip['id']}' ajouté à l'historique des publications.")
                        clips_published_count += 1 # Incrémente le compteur seulement si upload réussi
                    except Exception as e:
                        print(f"❌ Erreur lors de l'ajout/sauvegarde à l'historique après un upload réel: {e}")
                else:
                    print("❌ L'upload YouTube a échoué ou n'a pas retourné d'ID. Le Short n'a pas été publié sur YouTube.")
                    print("ℹ️ Le script continuera pour le prochain clip/l'artefact.")
            except Exception as e:
                print(f"❌ Une erreur inattendue est survenue pendant l'upload YouTube : {e}")
                print("ℹ️ Le script continuera pour le prochain clip/l'artefact.")
        else:
            print("❌ Service YouTube non authentifié. L'upload YouTube pour ce clip est ignoré.")
            print("ℹ️ Le script continuera pour le prochain clip/l'artefact.")

        # 9. Nettoyage des fichiers temporaires (uniquement le brut)
        print("🧹 Nettoyage des fichiers temporaires pour ce clip...")
        if os.path.exists(RAW_CLIP_PATH):
            os.remove(RAW_CLIP_PATH)
            print(f"  - Supprimé: {RAW_CLIP_PATH}")
        # Le PROCESSED_CLIP_PATH est laissé pour être collecté comme artefact par GitHub Actions.
        # Il sera écrasé lors de la prochaine itération ou du prochain run.

    # Résumé de l'exécution
    if clips_published_count == 0 and NUMBER_OF_CLIPS_TO_ATTEMPT_TO_PUBLISH > 0:
        print("\n🤷‍♂️ Aucune vidéo n'a pu être publiée avec succès lors de cette exécution.")
    elif clips_published_count > 0:
        print(f"\n🎉 {clips_published_count} Short(s) publié(s) avec succès lors de cette exécution.")
    
    print("✅ Workflow terminé.")

if __name__ == "__main__":
    main()
    print("DEBUG: Le script main.py s'est terminé sans erreur Python.")