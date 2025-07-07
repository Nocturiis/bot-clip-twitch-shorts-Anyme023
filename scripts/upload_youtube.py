# scripts/upload_youtube.py
import os
import google_auth_oauthlib.flow
import google.auth.transport.requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import json

# L'API scope nécessaire pour uploader des vidéos
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

# Chemin vers le fichier client_secret.json que vous avez téléchargé depuis Google Cloud Console
# Ce fichier NE DOIT PAS ÊTRE COMMITTÉ sur GitHub.
# Pour GitHub Actions, nous utiliserons un secret pour stocker son contenu.
CLIENT_SECRETS_FILE = 'client_secret.json' # Doit être au même niveau que le script ou un chemin défini.
# Le fichier token.json sera créé après la première authentification réussie
TOKEN_FILE = 'token.json'

def get_authenticated_service():
    """
    Authentifie l'utilisateur et retourne un objet de service YouTube.
    Gère le flux OAuth 2.0 et stocke les jetons d'accès.
    """
    credentials = None
    # Charger les jetons d'accès existants s'ils sont disponibles
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as token:
            credentials = google.oauth2.credentials.Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Si les jetons ne sont pas valides ou n'existent pas, lancer le flux d'authentification
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("🔑 Rafraîchissement du jeton d'accès YouTube...")
            credentials.refresh(google.auth.transport.requests.Request())
        else:
            print("🔑 Lancement du flux d'authentification YouTube...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob" # Pour les applications de bureau

            # Utilise un mode sans navigateur pour GitHub Actions si possible,
            # sinon, il faudra gérer le cas interactif localement.
            # Pour GitHub Actions, le client_secret.json doit être 'web' et le redirect_uri doit correspondre.
            # Ou, plus simple, utiliser un service account (mais non supporté pour les uploads directs)
            # ou un jeton pre-généré via OAuth 2.0 pour TV/Devices (plus complexe à setup).
            # Le plus simple pour GH Actions est de générer `token.json` localement une fois,
            # et de le stocker comme un secret crypté dans GH Actions.
            auth_url, _ = flow.authorization_url(prompt='consent')
            print(f"Veuillez ouvrir ce lien dans votre navigateur et autoriser l'application:\n{auth_url}")
            code = input("Entrez le code de vérification ici: ").strip()
            flow.fetch_token(code=code)
            credentials = flow.credentials

        # Sauvegarder les jetons pour les exécutions futures
        with open(TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())
        print("✅ Jeton d'accès YouTube sauvegardé.")

    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

def upload_youtube_short(youtube_service, video_path, metadata):
    """
    Uploade un fichier vidéo sur YouTube en tant que Short.

    Args:
        youtube_service: L'objet de service YouTube authentifié.
        video_path (str): Chemin vers le fichier vidéo à uploader.
        metadata (dict): Dictionnaire contenant le titre, la description, les tags, etc.

    Returns:
        str: L'ID de la vidéo YouTube uploadée si succès, sinon None.
    """
    print(f"📤 Démarrage de l'upload YouTube pour : {video_path}")
    if not os.path.exists(video_path):
        print(f"❌ Erreur : Le fichier vidéo n'existe pas à {video_path}")
        return None

    # Assurez-vous que les tags sont une liste et joignez-les en une seule chaîne
    tags_list = metadata.get('tags', [])
    if isinstance(tags_list, list):
        # Nettoyer chaque tag (supprimer les espaces en début/fin) et filtrer les tags vides
        processed_tags = [tag.strip() for tag in tags_list if tag.strip()]
        tags_string = ", ".join(processed_tags)
    else:
        # Si pour une raison quelconque ce n'est pas une liste (ce qui ne devrait plus arriver),
        # utilisez la valeur telle quelle.
        tags_string = str(tags_list) # Convertir en string pour éviter d'autres erreurs

    body = {
        'snippet': {
            'title': metadata['title'],
            'description': metadata['description'],
            'tags': tags_string, # CORRECTION ICI : Utilise la chaîne de tags
            'categoryId': metadata['categoryId'],
            'defaultLanguage': 'fr', # Ajout de la langue par défaut
            'defaultAudioLanguage': 'fr' # Ajout de la langue audio par défaut
        },
        'status': {
            'privacyStatus': metadata['privacyStatus'],
            'embeddable': metadata['embeddable'],
            'license': metadata['license'],
            'selfDeclaredMadeForKids': metadata['selfDeclaredMadeForKids']
        }
    }

    # Pour marquer comme Short, la vidéo doit être verticale (rapport 9:16) et <= 60s
    # Le code ne vérifie pas le rapport ici, il faut s'assurer que le clip source est bien vertical
    # ou que le traitement vidéo le convertit. YouTube le détecte automatiquement comme Short.

    media = MediaFileUpload(video_path, resumable=True)

    try:
        request = youtube_service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Progression de l'upload : {int(status.resumable_progress * 100)}%")
        
        video_id = response.get('id')
        print(f"✅ Vidéo uploadée avec succès ! ID de la vidéo : {video_id}")
        print(f"Lien : https://youtu.be/{video_id}")
        return video_id

    except HttpError as e:
        error_details = json.loads(e.content.decode('utf-8'))
        print(f"❌ Erreur lors de l'upload YouTube (HttpError) : {e}")
        print(f"Détails de l'erreur API : {error_details}")
        if 'error' in error_details and 'errors' in error_details['error']:
            for err in error_details['error']['errors']:
                print(f"  Raison: {err.get('reason')}")
                print(f"  Message: {err.get('message')}")
        return None
    except Exception as e:
        print(f"❌ Une erreur inattendue est survenue lors de l'upload : {e}")
        return None

if __name__ == "__main__":
    # Ce script est conçu pour être appelé par main.py
    print("Ce script est conçu pour être exécuté via main.py.")
    print("Pour une utilisation locale, assurez-vous que 'client_secret.json' est présent et configurez votre environnement.")
    
    # Pour le premier run local, vous devrez interagir pour l'authentification.
    # youtube = get_authenticated_service()
    
    # if youtube:
    #     print("Service YouTube prêt.")
    #     # Simulez des données de vidéo et un chemin de fichier
    #     # video_file_to_upload = os.path.join("data", "processed_clip_test.mp4") # Assurez-vous que ce fichier existe
    #     # if not os.path.exists(video_file_to_upload):
    #     #     print(f"Erreur: Le fichier '{video_file_to_upload}' n'existe pas pour le test d'upload.")
    #     # else:
    #     #     test_metadata = {
    #     #         "title": "Test Short par mon script Python",
    #     #         "description": "Ceci est un test d'upload de Short via un script Python.",
    #     #         "tags": ["test", "python", "youtube", "short"], # Doit être une liste ici pour le test
    #     #         "categoryId": "20", # Gaming
    #     #         "privacyStatus": "private", # Mettez en privé pour les tests
    #     #         "selfDeclaredMadeForKids": False,
    #     #         "embeddable": True,
    #     #         "license": "youtube"
    #     #     }
    #     #     uploaded_video_id = upload_youtube_short(youtube, video_file_to_upload, test_metadata)
    #     #     if uploaded_video_id:
    #     #         print(f"Test d'upload réussi. ID: {uploaded_video_id}")