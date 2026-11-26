# -*- coding: utf-8 -*-
"""Partie "moteur" : recherche YouTube, téléchargement et conversion (yt-dlp + ffmpeg)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

APP_NAME = "YouTube pour Resolve"
PAGE_SIZE = 24
MEDIA_EXT = {".mp4", ".mov", ".wav", ".mp3", ".m4a"}
IS_WIN = sys.platform.startswith("win")


# --------------------------------------------------------------------------- #
#  Emplacements : tout reste dans le dossier d'installation (ex. D:\YouTubePourResolve)
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent          # dossier d'installation
CACHE = ROOT / "cache"
THUMBS = CACHE / "thumbs"


def _writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        t = d / ".write_test"
        t.write_text("ok")
        t.unlink()
        return True
    except OSError:
        return False


if not _writable(ROOT):                                 # installation en lecture seule : repli
    ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YouTubePourResolve"
    CACHE, THUMBS = ROOT / "cache", ROOT / "cache" / "thumbs"
THUMBS.mkdir(parents=True, exist_ok=True)
# Deno (moteur JS de yt-dlp) met son cache ici plutôt que sur C:
os.environ.setdefault("DENO_DIR", str(CACHE / "deno"))


class Settings:
    FILE = ROOT / "settings.json"

    def __init__(self):
        self.download_dir = str(ROOT / "Telechargements")
        self.always_on_top = True
        self.cookies_browser = ""          # "", "firefox", "edge", "chrome", "brave", "opera"
        self.favorites: list[str] = []     # noms de fichiers
        self.history: list[str] = []       # recherches récentes ("mi:" devant = MyInstants)
        self.mi_region = "fr"              # pays des tendances MyInstants
        self.fast_download = True          # téléchargement multi-connexions
        self.connections = 8               # connexions simultanées par fichier
        self.preview_volume = 0.8          # volume de l'aperçu (0 à 1)
        self.ytdlp_channel = "stable"      # "stable" ou "nightly"
        self.ytdlp_auto_update = True      # mise à jour auto de yt-dlp au démarrage
        self.ytdlp_last_check = 0.0        # horodatage de la dernière vérification
        try:
            data = json.loads(self.FILE.read_text(encoding="utf-8"))
            self.__dict__.update({k: v for k, v in data.items() if k in self.__dict__})
        except Exception:
            pass

    def save(self):
        try:
            self.FILE.write_text(json.dumps(self.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


# --------------------------------------------------------------------------- #
#  Outils externes : ffmpeg (imageio-ffmpeg) et Deno (requis par yt-dlp)       #
# --------------------------------------------------------------------------- #
def ffmpeg_path() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        from shutil import which
        return which("ffmpeg")


def deno_path() -> str | None:
    try:
        import deno
        return deno.find_deno_bin()
    except Exception:
        from shutil import which
        return which("deno")


def _no_window_flags() -> dict:
    if IS_WIN:
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def probe_video_codec(path: str) -> str:
    """Renvoie le codec vidéo ('h264', 'vp9', 'av1'...) en lisant la sortie de ffmpeg -i."""
    ff = ffmpeg_path()
    if not ff:
        return ""
    r = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", **_no_window_flags())
    m = re.search(r"Stream #\S+.*?Video:\s*([A-Za-z0-9_]+)", r.stderr)
    return m.group(1).lower() if m else ""


_HW_ENCODERS: list | None = None


def h264_encoders() -> list[list[str]]:
    """Encodeurs H.264 à essayer, du plus rapide au plus sûr. La carte graphique
    (NVIDIA NVENC, Intel Quick Sync, AMD AMF) encode 5 à 10x plus vite, en qualité visuellement
    identique (débit constant élevé) ; sinon libx264 sur le processeur."""
    global _HW_ENCODERS
    if _HW_ENCODERS is None:
        candidates = [
            ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"],
            ["-c:v", "h264_qsv", "-global_quality", "19", "-preset", "medium"],
            ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "18", "-qp_p", "18"],
        ]
        ff, ok = ffmpeg_path(), []
        for c in candidates:
            try:
                r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                    "color=black:s=320x240:d=0.2", "-frames:v", "3", *c, "-f", "null", "-"],
                                   capture_output=True, timeout=20, **_no_window_flags())
                if r.returncode == 0:
                    ok.append(c)
            except Exception:
                pass
        _HW_ENCODERS = ok
    return _HW_ENCODERS + [["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]]


def reencode_to_h264(path: str, progress_cb=None) -> str:
    """Ré-encode en H.264/AAC (MP4) une vidéo que Resolve ne lit pas bien (VP9, AV1...)."""
    ff = ffmpeg_path()
    src = Path(path)
    tmp = src.with_name(src.stem + ".h264.tmp.mp4")
    if progress_cb:
        progress_cb(-1, "Conversion en H.264 pour Resolve…")
    r = None
    for venc in h264_encoders():
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), *venc,
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
               "-movflags", "+faststart", str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", **_no_window_flags())
        if r.returncode == 0 and tmp.exists():
            break
        tmp.unlink(missing_ok=True)
    if r is None or r.returncode != 0 or not tmp.exists():
        raise RuntimeError("Échec de la conversion H.264 : " + (r.stderr.strip()[-400:] if r else ""))
    final = src.with_suffix(".mp4")
    src.unlink(missing_ok=True)
    tmp.replace(final)
    return str(final)


# --------------------------------------------------------------------------- #
#  yt-dlp                                                                      #
# --------------------------------------------------------------------------- #
# Vidéo : H.264 (avc1) en priorité car Resolve ne décode pas le VP9 et mal l'AV1,
# audio AAC (m4a), le tout fusionné en MP4. La limite 1080p passe par le tri
# "res:1080", qui regarde le plus petit côté : un Short vertical 1080x1920 reste en 1080p.
VIDEO_FORMAT = ("bv*[vcodec^=avc1]+ba[ext=m4a]/bv*[vcodec^=avc1]+ba/b[vcodec^=avc1]/"
                "bv*+ba/b")
VIDEO_SORT = ["res:1080"]

MODES = {
    "video": ("Vidéo MP4 1080p", "Vidéo H.264 + son AAC, lisible par Resolve gratuit"),
    "wav": ("Audio WAV (recommandé)", "PCM 48 kHz / 16 bits, format natif de Resolve"),
    "mp3": ("Audio MP3", "Plus léger, 320 kb/s"),
}


def base_opts(settings: Settings) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
        "windowsfilenames": True,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "cachedir": str(CACHE / "yt-dlp"),
    }
    ff = ffmpeg_path()
    if ff:
        opts["ffmpeg_location"] = ff
    dn = deno_path()
    if dn:
        opts["js_runtimes"] = {"deno": {"path": dn}}
    if settings.cookies_browser:
        opts["cookiesfrombrowser"] = (settings.cookies_browser,)
    return opts


def is_url(text: str) -> bool:
    return bool(re.match(r"^(https?://)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", text.strip(), re.I))


def search_youtube(query: str, count: int, settings: Settings) -> list[dict]:
    import yt_dlp
    opts = dict(base_opts(settings), extract_flat="in_playlist", skip_download=True)
    opts.pop("cookiesfrombrowser", None)   # inutile pour une recherche, et plus rapide
    target = query.strip() if is_url(query) else f"ytsearch{count}:{query.strip()}"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
    entries = info.get("entries") if "entries" in info else [info]
    out = []
    for e in entries or []:
        if not e:
            continue
        vid = e.get("id")
        if not vid or e.get("ie_key") not in (None, "Youtube"):
            continue
        out.append({
            "id": vid,
            "title": e.get("title") or vid,
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": e.get("duration"),
            "views": e.get("view_count"),
            "url": e.get("webpage_url") or e.get("url") or f"https://www.youtube.com/watch?v={vid}",
            "live": e.get("live_status") in ("is_live", "is_upcoming"),
        })
    return out


def ytdlp_download(video: dict, mode: str, settings: Settings, progress_cb) -> str:
    """Méthode classique (yt-dlp seul). Sert de secours si le mode rapide échoue."""
    import yt_dlp
    out_dir = Path(settings.download_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = base_opts(settings)
    opts["outtmpl"] = str(out_dir / "%(title).150B [%(id)s].%(ext)s")

    if mode == "video":
        opts["format"] = VIDEO_FORMAT
        opts["format_sort"] = VIDEO_SORT
        opts["merge_output_format"] = "mp4"
        opts["postprocessor_args"] = {"merger": ["-movflags", "+faststart"]}
    else:
        opts["format"] = "bestaudio/best"
        codec = "wav" if mode == "wav" else "mp3"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": codec,
                                   "preferredquality": "320" if codec == "mp3" else "0"}]
        args = ["-ar", "48000"]
        args += ["-c:a", "pcm_s16le"] if codec == "wav" else []
        opts["postprocessor_args"] = {"extractaudio": args}
        # On suffixe le nom pour ne pas écraser la vidéo du même titre
        opts["outtmpl"] = str(out_dir / "%(title).150B [%(id)s] audio.%(ext)s")

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = int(done * 100 / total) if total else -1
            vcodec = (d.get("info_dict") or {}).get("vcodec")
            what = "vidéo" if mode == "video" and vcodec not in (None, "none") else "audio"
            progress_cb(pct, f"Téléchargement {what}…")
        elif d.get("status") == "finished":
            progress_cb(-1, "Finalisation…")

    def pp_hook(d):
        if d.get("status") == "started":
            names = {"Merger": "Assemblage vidéo + son…", "ExtractAudio": "Conversion audio…"}
            progress_cb(-1, names.get(d.get("postprocessor"), "Traitement…"))

    opts["progress_hooks"] = [hook]
    opts["postprocessor_hooks"] = [pp_hook]
    opts["concurrent_fragment_downloads"] = 8
    opts["http_chunk_size"] = 10 * 1024 * 1024

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video["url"], download=True)
    reqs = info.get("requested_downloads") or []
    path = (reqs[0].get("filepath") if reqs else None) or info.get("filepath")
    if not path or not Path(path).exists():
        raise RuntimeError("Le fichier téléchargé est introuvable.")

    if mode == "video":
        codec = probe_video_codec(path)
        if (codec and codec != "h264") or Path(path).suffix.lower() != ".mp4":
            path = reencode_to_h264(path, progress_cb)
    return path


# --------------------------------------------------------------------------- #
#  Téléchargement rapide : plusieurs connexions par fichier, vidéo et son en    #
#  même temps, puis assemblage SANS ré-encodage (qualité strictement identique) #
# --------------------------------------------------------------------------- #
class FastUnsupported(Exception):
    pass


def _http_session(headers: dict):
    import requests
    s = requests.Session()
    s.headers.update({k: v for k, v in (headers or {}).items() if k.lower() != "accept-encoding"})
    s.headers["Accept-Encoding"] = "identity"
    return s


def _probe_size(url: str, headers: dict) -> int:
    """Taille du fichier si le serveur accepte les requêtes par morceaux, sinon 0."""
    with _http_session(headers) as s:
        r = s.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=20)
        r.close()
        if r.status_code == 206:
            m = re.search(r"/(\d+)$", r.headers.get("Content-Range", ""))
            return int(m.group(1)) if m else 0
        if r.status_code >= 400:
            raise FastUnsupported(f"HTTP {r.status_code}")
    return 0


def ranged_download(url: str, headers: dict, dest: Path, total: int, on_bytes,
                    connections: int = 8, chunk: int = 4 * 1024 * 1024):
    """Télécharge `url` en morceaux de 4 Mo avec plusieurs connexions en parallèle."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    parts = [(a, min(a + chunk, total) - 1) for a in range(0, total, chunk)]
    lock = threading.Lock()
    local = threading.local()
    with open(dest, "wb") as f:
        f.truncate(total)

    def fetch(rng):
        a, b = rng
        if not hasattr(local, "s"):
            local.s = _http_session(headers)
        for attempt in range(5):
            got = 0
            try:
                r = local.s.get(url, headers={"Range": f"bytes={a}-{b}"}, stream=True, timeout=30)
                if r.status_code != 206:
                    raise IOError(f"HTTP {r.status_code}")
                buf = bytearray()
                for block in r.iter_content(256 * 1024):
                    buf += block
                    got += len(block)
                    on_bytes(len(block))
                if len(buf) != b - a + 1:
                    raise IOError("morceau incomplet")
                with lock:
                    with open(dest, "r+b") as f:
                        f.seek(a)
                        f.write(buf)
                return
            except Exception:
                on_bytes(-got)          # on retire ce qui a été compté pour ce morceau raté
                if attempt == 4:
                    raise
                import time
                time.sleep(1 + attempt)

    with ThreadPoolExecutor(max_workers=max(1, connections)) as ex:
        for fut in [ex.submit(fetch, p) for p in parts]:
            fut.result()


def _safe_name(title: str, vid: str, suffix: str = "") -> str:
    from yt_dlp.utils import sanitize_filename
    t = sanitize_filename(title or vid, restricted=False)
    t = t.encode("utf-8")[:150].decode("utf-8", "ignore").strip() or vid
    return f"{t} [{vid}]{suffix}"


def _run_ffmpeg(args: list[str], what: str):
    r = subprocess.run([ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       **_no_window_flags())
    if r.returncode != 0:
        raise RuntimeError(f"{what} : " + r.stderr.strip()[-300:])


def fast_download(video: dict, mode: str, settings: Settings, progress_cb) -> str:
    import threading
    import time
    import yt_dlp
    out_dir = Path(settings.download_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = base_opts(settings)
    if mode == "video":
        opts["format"], opts["format_sort"] = VIDEO_FORMAT, VIDEO_SORT
    else:
        opts["format"] = "bestaudio/best"
    progress_cb(-1, "Analyse de la vidéo…")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video["url"], download=False)
    fmts = info.get("requested_formats") or [info]
    for f in fmts:
        if f.get("protocol") not in ("https", "http") or not f.get("url"):
            raise FastUnsupported(f"protocole {f.get('protocol')}")
    sizes = [_probe_size(f["url"], f.get("http_headers")) for f in fmts]
    if not all(sizes):
        raise FastUnsupported("pas de téléchargement par morceaux")

    vid = info.get("id") or video.get("id") or "video"
    title = info.get("title") or video.get("title") or vid
    tmp_dir = out_dir / ".en-cours"
    tmp_dir.mkdir(exist_ok=True)
    parts = [tmp_dir / f"{vid}.f{f.get('format_id', i)}.{f.get('ext') or 'bin'}" for i, f in enumerate(fmts)]
    total, done = sum(sizes), [0]
    lock = threading.Lock()
    t0, last = time.time(), [0.0]

    def on_bytes(n):
        with lock:
            done[0] += n
            now = time.time()
            if now - last[0] > 0.25:
                last[0] = now
                speed = done[0] / max(now - t0, 0.001) / 1048576
                progress_cb(int(done[0] * 100 / total), f"Téléchargement… {speed:.1f} Mo/s".replace(".", ","))

    errors = []

    def one(i):
        try:
            ranged_download(fmts[i]["url"], fmts[i].get("http_headers"), parts[i], sizes[i], on_bytes,
                            connections=settings.connections)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=one, args=(i,), daemon=True) for i in range(len(fmts))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        if errors:
            raise errors[0]
        if mode == "video":
            progress_cb(-1, "Assemblage vidéo + son (sans perte)…")
            out = out_dir / (_safe_name(title, vid) + ".mp4")
            args = []
            for p_ in parts:
                args += ["-i", str(p_)]
            if len(parts) == 2:
                args += ["-map", "0:v:0", "-map", "1:a:0"]
            _run_ffmpeg([*args, "-c", "copy", "-movflags", "+faststart", str(out)], "Assemblage")
            codec = probe_video_codec(str(out))
            if codec and codec != "h264":
                return reencode_to_h264(str(out), progress_cb)
            return str(out)
        progress_cb(-1, "Conversion audio…")
        ext = "wav" if mode == "wav" else "mp3"
        out = out_dir / (_safe_name(title, vid, " audio") + "." + ext)
        codec = ["-c:a", "pcm_s16le"] if ext == "wav" else ["-c:a", "libmp3lame", "-b:a", "320k"]
        _run_ffmpeg(["-i", str(parts[-1]), "-vn", "-ar", "48000", *codec, str(out)], "Conversion audio")
        return str(out)
    finally:
        for p_ in parts:
            p_.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except OSError:
            pass


def download(video: dict, mode: str, settings: Settings, progress_cb) -> str:
    """Mode rapide d'abord ; en cas de souci, on retombe sur yt-dlp classique."""
    if settings.fast_download:
        try:
            return fast_download(video, mode, settings, progress_cb)
        except Exception as e:  # noqa: BLE001
            low = str(e).lower()
            if "not a bot" in low or "sign in" in low or "private" in low:
                raise                    # inutile de réessayer autrement
            log_error(f"Mode rapide indisponible pour {video.get('url')} -> méthode classique\n"
                      f"{traceback.format_exc()}")
            progress_cb(-1, "Téléchargement (mode classique)…")
    return ytdlp_download(video, mode, settings, progress_cb)


# --------------------------------------------------------------------------- #
#  Aperçu : petit flux 360p (image + son) lu directement, sans téléchargement   #
# --------------------------------------------------------------------------- #
def preview_stream(video: dict, settings: Settings) -> dict:
    import yt_dlp
    opts = dict(base_opts(settings),
                format="18/b[height<=480][vcodec!=none][acodec!=none]/ba[ext=m4a]/ba/b")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video["url"], download=False)
    f = (info.get("requested_formats") or [info])[0]
    return {"url": f["url"], "has_video": f.get("vcodec") not in (None, "none"),
            "duration": info.get("duration")}


# --------------------------------------------------------------------------- #
#  MyInstants                                                                  #
# --------------------------------------------------------------------------- #
MI_BASE = "https://www.myinstants.com"
MI_LISTS = [  # (clé, libellé)
    ("trending", "Tendances"), ("best", "Les meilleurs"), ("recent", "Récents"),
    ("cat:sound effects", "Sound Effects"), ("cat:memes", "Memes"), ("cat:reactions", "Réactions"),
    ("cat:viral", "Viral"), ("cat:tiktok trends", "Tendances TikTok"), ("cat:games", "Jeux vidéo"),
    ("cat:movies", "Films"), ("cat:television", "Télévision"), ("cat:music", "Musique"),
    ("cat:anime & manga", "Anime & Manga"), ("cat:sports", "Sports"), ("cat:pranks", "Blagues"),
    ("cat:politics", "Politique"), ("cat:whatsapp audios", "Audios WhatsApp"),
]
MI_REGIONS = [("fr", "France"), ("be", "Belgique"), ("ch", "Suisse"), ("ca", "Canada"), ("us", "États-Unis"),
              ("gb", "Royaume-Uni"), ("br", "Brésil"), ("es", "Espagne"), ("de", "Allemagne"), ("it", "Italie")]
MI_PAGE = 36
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/130.0 Safari/537.36")


def myinstants_list(source: str, query: str, page: int, region: str = "fr") -> list[dict]:
    """source = clé de MI_LISTS ; si query est rempli, c'est une recherche."""
    import html
    from urllib.parse import quote
    import requests
    region = region or "fr"
    if query:
        url, params = f"{MI_BASE}/en/search/", {"name": query, "page": page}
    elif source == "best":
        url, params = f"{MI_BASE}/en/best_of_all_time/{region}/", {"page": page}
    elif source == "recent":
        url, params = f"{MI_BASE}/en/recent/", {"page": page}
    elif source.startswith("cat:"):
        url, params = f"{MI_BASE}/en/categories/{quote(source[4:])}/{region}/", {"page": page}
    else:
        url, params = f"{MI_BASE}/en/trending/{region}/", {"page": page}
    r = requests.get(url, params=params, headers={"User-Agent": _UA, "Accept-Language": "fr,en;q=0.8"},
                     timeout=20)
    if r.status_code == 404:
        return []                     # au-delà de la dernière page
    r.raise_for_status()
    out = []
    for block in r.text.split('<div class="instant">')[1:]:
        mp3 = re.search(r"play\('([^']+\.mp3)'", block)
        if not mp3:
            continue
        title = re.search(r'class="instant-link[^"]*"[^>]*>([^<]*)<', block)
        slug = re.search(r'href="/[a-z]{2}/instant/([^"/]+)/"', block)
        color = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,6})", block)
        ident = re.search(r"loader-(\d+)", block)
        out.append({
            "id": "mi" + (ident.group(1) if ident else mp3.group(1)),
            "title": html.unescape(title.group(1)).strip() if title else Path(mp3.group(1)).stem,
            "mp3": MI_BASE + mp3.group(1),
            "page_url": f"{MI_BASE}/en/instant/{slug.group(1)}/" if slug else MI_BASE,
            "color": color.group(1) if color else "#ff3b3b",
        })
    return out


def myinstants_download(item: dict, mode: str, settings: Settings, progress_cb=None) -> str:
    import requests
    out_dir = Path(settings.download_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    from yt_dlp.utils import sanitize_filename
    base = sanitize_filename(item["title"], restricted=False).strip() or item["id"]
    base = base.encode("utf-8")[:120].decode("utf-8", "ignore") + " [myinstants]"
    ext = "wav" if mode == "wav" else "mp3"
    out = out_dir / f"{base}.{ext}"
    if out.exists() and out.stat().st_size > 0:
        return str(out)
    if progress_cb:
        progress_cb(-1, "Téléchargement…")
    r = requests.get(item["mp3"], headers={"User-Agent": _UA, "Referer": MI_BASE + "/"}, timeout=30)
    r.raise_for_status()
    if ext == "mp3":
        out.write_bytes(r.content)
        return str(out)
    tmp = out_dir / f".{item['id']}.mp3"
    tmp.write_bytes(r.content)
    try:
        if progress_cb:
            progress_cb(-1, "Conversion WAV…")
        _run_ffmpeg(["-i", str(tmp), "-vn", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)],
                    "Conversion WAV")
    finally:
        tmp.unlink(missing_ok=True)
    return str(out)


# --------------------------------------------------------------------------- #
#  Mise à jour de yt-dlp (le "moteur" YouTube) depuis l'application            #
# --------------------------------------------------------------------------- #
def _vtuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4])


def ytdlp_installed_version() -> str:
    """Version présente sur le disque (relue à chaque appel, donc juste après une mise à jour)."""
    try:
        import importlib.metadata as md
        return md.version("yt-dlp")
    except Exception:
        try:
            import yt_dlp
            return yt_dlp.version.__version__
        except Exception:
            return "?"


def ytdlp_latest_versions() -> dict:
    """Dernières versions publiées sur PyPI : {"stable": "2026.11.23", "nightly": "2026.11.24.23…dev0"}."""
    import requests
    r = requests.get("https://pypi.org/pypi/yt-dlp/json", timeout=15)
    r.raise_for_status()
    data = r.json()
    stable = data["info"]["version"]
    releases = [v for v, files in data.get("releases", {}).items() if files]
    nightly = max(releases + [stable], key=_vtuple)
    return {"stable": stable, "nightly": nightly}


def ytdlp_update_available(channel: str) -> str | None:
    """Renvoie la version à installer si elle est plus récente que celle installée, sinon None."""
    latest = ytdlp_latest_versions()
    target = latest["nightly" if channel == "nightly" else "stable"]
    return target if _vtuple(target) > _vtuple(ytdlp_installed_version()) else None


def _pip_python() -> str:
    """python.exe à côté de pythonw.exe (pip a besoin de la version console)."""
    exe = Path(sys.executable)
    cand = exe.with_name("python.exe") if exe.name.lower() == "pythonw.exe" else exe
    return str(cand if cand.exists() else exe)


def update_ytdlp(channel: str = "stable", progress_cb=None) -> dict:
    """Installe la dernière version de yt-dlp (+ son solveur JS et Deno) dans le Python de l'application.
    La fenêtre doit ensuite redémarrer pour charger la nouvelle version (yt-dlp ne se recharge pas à chaud)."""
    before = ytdlp_installed_version()
    latest = ytdlp_latest_versions()
    if progress_cb:
        progress_cb(-1, "Téléchargement de la mise à jour…")
    tmp = ROOT / "tmp"
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ, TEMP=str(tmp), TMP=str(tmp), PIP_DISABLE_PIP_VERSION_CHECK="1")
    cmd = [_pip_python(), "-m", "pip", "install", "--upgrade", "--no-cache-dir",
           "--no-warn-script-location", "--disable-pip-version-check"]
    if channel == "nightly":
        cmd += ["--pre", "yt-dlp[default]"]
    else:
        # version stable exacte : permet aussi de revenir de nightly à stable
        cmd += [f"yt-dlp[default]=={latest['stable']}"]
    cmd += ["yt-dlp-ejs", "deno"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=600, **_no_window_flags())
    try:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    if r.returncode != 0:
        log_error("Mise à jour yt-dlp échouée\n" + r.stdout[-3000:] + "\n" + r.stderr[-3000:])
        last = [l for l in (r.stderr or r.stdout).strip().splitlines() if l.strip()][-1:] or ["erreur inconnue"]
        raise RuntimeError("La mise à jour a échoué : " + last[0][-250:])
    after = ytdlp_installed_version()
    return {"before": before, "after": after, "changed": after != before}


def friendly_error(exc: BaseException) -> str:
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).replace("ERROR: ", "")
    low = msg.lower()
    if "not a bot" in low or "sign in to confirm" in low:
        return ("YouTube demande une vérification anti-robot. Ouvre ⚙ Réglages et choisis "
                "le navigateur où tu es connecté à YouTube (Firefox conseillé), puis réessaie.")
    if "age" in low and ("restricted" in low or "confirm your age" in low):
        return "Vidéo soumise à une limite d'âge : choisis un navigateur connecté dans ⚙ Réglages."
    if "private video" in low:
        return "Cette vidéo est privée."
    if "could not copy" in low and "cookie" in low:
        return ("Impossible de lire les cookies du navigateur : ferme complètement ce navigateur "
                "puis réessaie (ou choisis Firefox).")
    if "unable to download" in low or "http error" in low or "timed out" in low:
        return ("Problème réseau, ou YouTube a changé : ⚙ Réglages > « Mettre à jour yt-dlp », puis réessaie.\n"
                + msg[-300:])
    return msg[-500:]


# --------------------------------------------------------------------------- #
#  Tâches en arrière-plan                                                      #
# --------------------------------------------------------------------------- #
LOG_FILE = CACHE / "erreurs.log"


def log_error(text: str):
    """Garde une trace des erreurs (utile pour le dépannage) dans cache/erreurs.log."""
    try:
        import datetime
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
        if LOG_FILE.stat().st_size > 2_000_000:
            LOG_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass


class Bridge(QObject):
    """Pont unique entre les threads de travail et la fenêtre.

    Il vit dans le thread de l'interface : les signaux émis depuis un thread de travail
    sont donc remis en file et traités dans le thread de l'interface (jamais ailleurs)."""
    done = Signal(int, object)
    failed = Signal(int, str)
    progress = Signal(int, int, str)


class Task(QRunnable):
    """Exécute fn(*args) dans un thread et renvoie le résultat via le Bridge, avec un numéro."""

    def __init__(self, task_id: int, bridge: Bridge, fn, *args, with_progress=False):
        super().__init__()
        self.setAutoDelete(False)          # Python garde la main sur la durée de vie
        self.task_id, self.bridge = task_id, bridge
        self.fn, self.args, self.with_progress = fn, args, with_progress

    def run(self):
        tid, bridge = self.task_id, self.bridge
        try:
            extra = ((lambda pct, txt: bridge.progress.emit(tid, int(pct), str(txt))),) \
                if self.with_progress else ()
            result = self.fn(*self.args, *extra)
        except Exception as e:  # noqa: BLE001
            log_error(f"{getattr(self.fn, '__name__', self.fn)}{self.args[:2]}\n{traceback.format_exc()}")
            bridge.failed.emit(tid, friendly_error(e))
            return
        bridge.done.emit(tid, result)


# --------------------------------------------------------------------------- #
#  Relais local pour l'aperçu : le lecteur lit http://127.0.0.1:port/... et le #
#  relais va chercher le flux https (YouTube / MyInstants) avec les en-têtes   #
#  qu'il faut. Évite toute dépendance au support TLS du lecteur Qt.            #
# --------------------------------------------------------------------------- #
class StreamRelay:
    def __init__(self):
        import http.server
        import threading
        from urllib.parse import parse_qs, urlparse
        import requests
        relay = self
        self.urls: dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = _UA

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                key = parse_qs(urlparse(self.path).query).get("k", [""])[0]
                url = relay.urls.get(key)
                if not url:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                headers = {"Accept-Encoding": "identity"}
                if self.headers.get("Range"):
                    headers["Range"] = self.headers["Range"]
                try:
                    r = relay.session.get(url, headers=headers, stream=True, timeout=20)
                except Exception:
                    self.send_response(502)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(r.status_code)
                for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                    if r.headers.get(h):
                        self.send_header(h, r.headers[h])
                self.end_headers()
                try:
                    for chunk in r.iter_content(64 * 1024):
                        self.wfile.write(chunk)
                except Exception:
                    pass                # le lecteur a coupé (pause, avance rapide…)
                finally:
                    r.close()

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def local_url(self, url: str) -> str:
        import hashlib
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        self.urls[key] = url
        return f"http://127.0.0.1:{self.server.server_address[1]}/stream?k={key}"
