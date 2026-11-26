# YouTube pour Resolve

Fenêtre compagnon pour DaVinci Resolve (version gratuite incluse) : rechercher des vidéos YouTube
et des sons MyInstants, les prévisualiser, les télécharger (MP4 1080p H.264, WAV 48 kHz, MP3)
puis les glisser-déposer sur la timeline.

## Installation (Windows 10/11)

1. Télécharge le dépôt (bouton **Code > Download ZIP**) et décompresse-le.
2. Double-clique sur `Installer.bat` et accepte le dossier proposé (`D:\YouTubePourResolve`).
   Python portable, yt-dlp, ffmpeg et Deno sont installés **dans ce dossier**, rien sur C:.
3. Lance l'application depuis le raccourci du Bureau, ou dans Resolve :
   **Workspace > Scripts > YouTube_pour_Resolve**.

Mode d'emploi complet : [LISEZMOI.txt](LISEZMOI.txt).

## Fonctions

- Recherche YouTube avec miniatures, tri et chargement continu.
- Onglet MyInstants : tendances, catégories, recherche, écoute immédiate.
- Aperçu intégré (vidéo 360p avec le son) avant de télécharger.
- Téléchargement rapide multi-connexions, assemblé sans ré-encodage (qualité identique).
- Vidéo MP4 1080p H.264 + AAC (conversion automatique si besoin), audio WAV 48 kHz ou MP3.
- Glisser-déposer direct vers la timeline ou le Media Pool de Resolve.
- Mise à jour de yt-dlp depuis les Réglages (canal Stable ou Nightly), automatique au démarrage.

## Structure

| Chemin | Rôle |
| --- | --- |
| `app/yt_resolve.py` | Interface (PySide6) |
| `app/core.py` | Recherche, téléchargement, MyInstants, mise à jour de yt-dlp |
| `app/requirements.txt` | Dépendances Python |
| `Installer.bat` | Installation sur le disque choisi (D: par défaut) |
| `scripts/` | Lancer, mettre à jour, désinstaller (copiés dans le dossier d'installation) |

N'utilise pas l'API de scripting de Resolve (réservée à Studio) : marche avec la version gratuite.
Ne télécharge que des contenus que tu as le droit d'utiliser.
