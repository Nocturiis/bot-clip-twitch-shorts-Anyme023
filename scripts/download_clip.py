# scripts/download_clip.py
import subprocess
import sys
import os

def download_twitch_clip(clip_url, output_path):
    """
    Télécharge un clip Twitch en utilisant yt-dlp.
    Le clip est enregistré au format MP4.

    Args:
        clip_url (str): L'URL complète du clip Twitch (ex: https://www.twitch.tv/CLIP_ID).
        output_path (str): Le chemin complet où le fichier vidéo doit être sauvegardé.

    Returns:
        str: Le chemin du fichier téléchargé si le téléchargement est réussi, sinon None.
    """
    print(f"📥 Téléchargement du clip Twitch depuis : {clip_url}")
    print(f"Destination : {output_path}")

    # Assurez-vous que le répertoire de destination existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        # Commande yt-dlp pour télécharger la meilleure qualité vidéo disponible
        # La durée max de youtube-dl est 1h, donc ça coupe automatiquement la vidéo à 1h
        command = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--output", output_path,
            clip_url
        ]
        
        # Exécute la commande en temps réel pour voir la progression
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='') # Affiche la sortie de yt-dlp en temps réel

        process.wait() # Attend que le processus se termine

        if process.returncode == 0:
            print(f"✅ Clip téléchargé avec succès vers : {output_path}")
            return output_path
        else:
            print(f"❌ Erreur lors du téléchargement du clip. Code de retour : {process.returncode}")
            return None
    except FileNotFoundError:
        print("❌ Erreur : yt-dlp n'est pas trouvé. Assurez-vous qu'il est installé (pip install yt-dlp).")
        return None
    except Exception as e:
        print(f"❌ Une erreur inattendue est survenue lors du téléchargement : {e}")
        return None

if __name__ == "__main__":
    # Exemple d'utilisation (pour les tests locaux)
    # Ce script est destiné à être appelé par main.py
    print("Ce script est conçu pour être exécuté via main.py.")
    print("Si vous le testez directement, assurez-vous d'avoir un CLIP_URL valide.")
    # clip_url_test = "https://www.twitch.tv/Gotaga/clip/DignifiedPoliteTrollBudBlast-u-U6k-n2b7v2vX7Z" 
    # output_file_test = os.path.join("data", "downloaded_clip_test.mp4")
    # downloaded_file = download_twitch_clip(clip_url_test, output_file_test)
    # if downloaded_file:
    #     print(f"Test download complete: {downloaded_file}")