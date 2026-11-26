# -*- coding: utf-8 -*-
"""
YouTube pour Resolve
--------------------
Fenêtre compagnon pour DaVinci Resolve (version gratuite incluse) :
  - rechercher des vidéos YouTube et les sons de MyInstants,
  - les écouter / regarder en aperçu,
  - les télécharger (MP4 1080p H.264 + AAC, WAV 48 kHz, MP3),
  - les glisser-déposer sur la timeline ou dans le Media Pool.
N'utilise pas l'API de scripting de Resolve (réservée à Studio).
"""
from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import (QByteArray, QFileSystemWatcher, QMimeData, QPoint, QProcess,
                            QRect, QRectF, QSize, Qt, QThreadPool, QTimer,
                            QUrl, Signal)
from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QDrag, QFont,
                           QFontMetrics, QGuiApplication, QIcon, QKeySequence,
                           QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QRadialGradient, QShortcut)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtNetwork import (QLocalServer, QLocalSocket,
                               QNetworkAccessManager, QNetworkReply,
                               QNetworkRequest)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup,
                               QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListView, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea,
                               QSlider, QStackedWidget, QStyle,
                               QStyledItemDelegate, QToolButton, QVBoxLayout,
                               QWidget)

import core
from core import (APP_NAME, IS_WIN, MEDIA_EXT, MI_LISTS, MI_PAGE, MI_REGIONS,
                  MODES, PAGE_SIZE, ROOT, THUMBS, Bridge, Settings,
                  StreamRelay, Task, deno_path, download, ffmpeg_path, is_url,
                  log_error, myinstants_download, myinstants_list,
                  preview_stream, search_youtube, update_ytdlp,
                  ytdlp_installed_version, ytdlp_latest_versions,
                  ytdlp_update_available)
import time

# --------------------------------------------------------------------------- #
#  Couleurs & icônes                                                           #
# --------------------------------------------------------------------------- #
BG = "#161618"
PANEL = "#1b1b1e"
CARD = "#202024"
CARD_HOVER = "#27272c"
LINE = "#2a2a2e"
TEXT = "#e8e8ea"
MUTED = "#8d8d94"
ACCENT = "#c3f03a"          # vert citron
ACCENT_TEXT = "#121212"
RED = "#ff6b6b"
GREEN = "#5fd38d"
STAR = "#ffd24a"

_GEAR = ("M12.00 2.50 L13.85 2.68 L13.40 4.94 L15.60 5.85 L16.88 3.94 L18.32 5.12 L19.50 6.56 "
         "L17.59 7.84 L18.50 10.04 L20.76 9.59 L20.94 11.44 L20.94 12.56 L20.76 14.41 L18.50 13.96 "
         "L17.59 16.16 L19.50 17.44 L18.32 18.88 L16.88 20.06 L15.60 18.15 L13.40 19.06 L13.85 21.32 "
         "L12.00 21.50 L10.15 21.32 L10.60 19.06 L8.40 18.15 L7.12 20.06 L5.68 18.88 L4.50 17.44 "
         "L6.41 16.16 L5.50 13.96 L3.24 14.41 L3.06 12.56 L3.06 11.44 L3.24 9.59 L5.50 10.04 L6.41 7.84 "
         "L4.50 6.56 L5.68 5.12 L7.12 3.94 L8.40 5.85 L10.60 4.94 L10.15 2.68 Z")
_ICONS = {
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "gear": f'<path d="{_GEAR}"/><circle cx="12" cy="12" r="3"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21"/>',
    "star": '<path d="M12 3l2.8 5.9 6.2.6-4.7 4.3 1.3 6.2L12 16.8 6.4 20l1.3-6.2L3 9.5l6.2-.6z"/>',
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "film": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
    "music": '<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
    "youtube": '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="M10 9l5 3-5 3z" fill="{c}"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "button": '<circle cx="12" cy="13" r="8"/><path d="M6 13a6 6 0 0 1 12 0"/><path d="M4 13v2a8 4 0 0 0 16 0v-2"/>',
    "play": '<path d="M8 5l11 7-11 7z" fill="{c}"/>',
    "pause": '<path d="M8 5v14M16 5v14" stroke-width="3"/>',
    "volume": '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
}


def svg_pixmap(name: str, color: str, size: int = 18, fill: str = "none", dpr: float = 2.0,
               opacity: float = 1.0) -> QPixmap:
    body = _ICONS[name].replace("{c}", color)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{fill}" stroke="{color}" '
           f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setOpacity(opacity)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def svg_icon(name: str, color: str = MUTED, size: int = 18, fill: str = "none") -> QIcon:
    return QIcon(svg_pixmap(name, color, size, fill))


def app_icon() -> QIcon:
    pm = QPixmap(128, 128)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(ACCENT))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(8, 8, 112, 112, 28, 28)
    path = QPainterPath()
    path.moveTo(50, 38)
    path.lineTo(90, 64)
    path.lineTo(50, 90)
    path.closeSubpath()
    p.setBrush(QColor("#151517"))
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def draw_instant_button(p: QPainter, center: QPoint, r: int, color: str):
    """Dessine un bouton rond façon "soundboard" (couleur du son MyInstants)."""
    c = QColor(color)
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 120))
    p.drawEllipse(QRectF(center.x() - r, center.y() - r + 6, 2 * r, 2 * r))
    p.setBrush(c.darker(160))
    p.drawEllipse(QRectF(center.x() - r, center.y() - r + 4, 2 * r, 2 * r))
    g = QRadialGradient(center.x() - r * 0.35, center.y() - r * 0.45, r * 1.6)
    g.setColorAt(0, c.lighter(135))
    g.setColorAt(0.6, c)
    g.setColorAt(1, c.darker(125))
    p.setBrush(QBrush(g))
    p.drawEllipse(QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r))
    p.restore()


def instant_cover(color: str, w: int = 320, h: int = 180) -> QPixmap:
    pm = QPixmap(w, h)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#24242a"))
    g.setColorAt(1, QColor("#121215"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.fillRect(pm.rect(), QBrush(g))
    draw_instant_button(p, QPoint(w // 2, h // 2 - 4), int(h * 0.3), color)
    p.end()
    return pm


# --------------------------------------------------------------------------- #
#  Utilitaires                                                                 #
# --------------------------------------------------------------------------- #
def fmt_duration(sec) -> str:
    if not sec:
        return ""
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_views(n) -> str:
    if not n:
        return ""
    for div, suf in ((1e9, " Md"), (1e6, " M"), (1e3, " k")):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".").replace(".", ",") + suf + " vues"
    return f"{n} vues"


def fmt_size(b: int) -> str:
    mb = b / 1048576
    return (f"{mb:.1f}".replace(".", ",") + " Mo") if mb < 1024 else (f"{mb / 1024:.2f}".replace(".", ",") + " Go")


def is_video_file(p: str) -> bool:
    return Path(p).suffix.lower() in (".mp4", ".mov")


def reveal_in_explorer(path: str):
    p = Path(path)
    if IS_WIN:
        subprocess.Popen(["explorer", "/select,", str(p)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))


def video_frame_thumb(path: str, out: str) -> str:
    """Extrait une image d'une vidéo (pour les fichiers ajoutés à la main dans le dossier)."""
    ff = ffmpeg_path()
    for ss in ("1", "0"):
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-ss", ss, "-i", path,
                        "-frames:v", "1", "-vf", "scale=320:-2", out],
                       capture_output=True, **core._no_window_flags())
        if Path(out).exists():
            return out
    raise RuntimeError("pas d'image")


# --------------------------------------------------------------------------- #
#  Données des vignettes                                                       #
# --------------------------------------------------------------------------- #
ROLE = Qt.UserRole + 1
CARD_W, CARD_H = 212, 188
_WIN = None   # fenêtre principale (pour relire l'état vivant d'une vignette)


def tile_data(obj) -> dict | None:
    """Qt copie les données des éléments : pour YouTube / MyInstants on ne stocke que l'id
    et on relit l'état à jour (progression, fichiers…) dans la fenêtre."""
    raw = obj.data(ROLE)
    if raw and _WIN is not None:
        if raw.get("kind") == "yt":
            return _WIN.videos.get(raw["id"], raw)
        if raw.get("kind") == "mi":
            return _WIN.instants.get(raw["id"], raw)
    return raw


def tile_key(d: dict) -> str:
    if d["kind"] == "yt":
        return "yt:" + d["video"]["id"]
    if d["kind"] == "mi":
        return d["item"]["id"]
    return "file:" + d["path"]


def tile_title(d: dict) -> str:
    if d["kind"] == "yt":
        return d["video"]["title"]
    if d["kind"] == "mi":
        return d["item"]["title"]
    return Path(d["path"]).stem


# --------------------------------------------------------------------------- #
#  Grille de vignettes                                                         #
# --------------------------------------------------------------------------- #
class TileDelegate(QStyledItemDelegate):
    """Dessine une vignette : image, badge, durée, ▶ aperçu, bouton (télécharger / étoile), titre."""
    button_clicked = Signal(object, QPoint)       # (élément, position globale)
    play_clicked = Signal(object)

    def __init__(self, win: "MainWindow", view: QListWidget):
        super().__init__(view)
        self.win, self.view = win, view
        base = QApplication.font()
        self.f_title = QFont(base)
        self.f_title.setPixelSize(13)
        self.f_title.setWeight(QFont.DemiBold)
        self.f_small = QFont(base)
        self.f_small.setPixelSize(11)
        self.f_badge = QFont(base)
        self.f_badge.setPixelSize(11)
        self.f_badge.setWeight(QFont.DemiBold)
        self.f_big = QFont(base)
        self.f_big.setPixelSize(18)
        self.f_big.setWeight(QFont.Bold)

    def sizeHint(self, option, index):
        return QSize(CARD_W, CARD_H)

    @staticmethod
    def geometry(r: QRect):
        card = r.adjusted(5, 5, -5, -5)
        tw = card.width() - 20
        thumb = QRect(card.x() + 10, card.y() + 10, tw, round(tw * 9 / 16))
        btn = QRect(thumb.right() - 31, thumb.y() + 6, 26, 26)
        play = QRect(0, 0, 46, 46)
        play.moveCenter(thumb.center())
        return card, thumb, btn, play

    def _pill(self, p: QPainter, x, y, text, bg, fg="#ffffff", right=False):
        p.setFont(self.f_badge)
        fm = QFontMetrics(p.font())
        w, h = fm.horizontalAdvance(text) + 12, fm.height() + 4
        rect = QRect(x - w if right else x, y, w, h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(bg))
        p.drawRoundedRect(rect, 4, 4)
        p.setPen(QColor(fg))
        p.drawText(rect, Qt.AlignCenter, text)
        return rect

    def paint(self, p: QPainter, opt, index):
        d = tile_data(index)
        if not d:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        hovered = bool(opt.state & QStyle.State_MouseOver)
        selected = bool(opt.state & QStyle.State_Selected)
        card, thumb, btn, play = self.geometry(opt.rect)
        kind = d["kind"]
        state = d.get("state", "")
        previewing = self.win.preview_key == tile_key(d)
        playing = previewing and self.win.preview.is_playing()

        # carte
        p.setPen(QPen(QColor(ACCENT), 1.5) if (selected or previewing) else Qt.NoPen)
        p.setBrush(QColor(CARD_HOVER if (hovered or selected) else CARD))
        p.drawRoundedRect(QRectF(card).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        # image
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(thumb), 6, 6)
        p.save()
        p.setClipPath(clip)
        if kind == "mi":
            g = QLinearGradient(QRectF(thumb).topLeft(), QRectF(thumb).bottomRight())
            g.setColorAt(0, QColor("#2a2a31"))
            g.setColorAt(1, QColor("#141418"))
            p.fillRect(thumb, QBrush(g))
            draw_instant_button(p, thumb.center() - QPoint(0, 3), 30, d["item"]["color"])
        else:
            pm = self.win.thumb_for(d)
            if pm and not pm.isNull():
                scaled = pm.scaled(thumb.size() * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                sx = (scaled.width() - thumb.width() * 2) // 2
                sy = (scaled.height() - thumb.height() * 2) // 2
                p.drawPixmap(thumb, scaled, QRect(sx, sy, thumb.width() * 2, thumb.height() * 2))
            else:
                audio = kind == "file" and not is_video_file(d["path"])
                g = QLinearGradient(QRectF(thumb).topLeft(), QRectF(thumb).bottomRight())
                g.setColorAt(0, QColor("#3a1d5c" if audio else "#1f2a3a"))
                g.setColorAt(1, QColor("#12081f" if audio else "#0d1118"))
                p.fillRect(thumb, QBrush(g))
                ic = svg_pixmap("music" if audio else ("youtube" if kind == "yt" else "film"), "#ffffff", 34,
                                opacity=0.55)
                p.drawPixmap(thumb.center() - QPoint(17, 17), ic)

        if state == "downloading":
            p.fillRect(thumb, QColor(0, 0, 0, 150))
            p.setPen(QColor("#ffffff"))
            p.setFont(self.f_big)
            pct = d.get("pct", -1)
            p.drawText(thumb.adjusted(0, -10, 0, -10), Qt.AlignCenter, f"{pct} %" if pct >= 0 else "…")
            p.setFont(self.f_small)
            p.setPen(QColor("#dddddd"))
            p.drawText(thumb.adjusted(6, 22, -6, 0), Qt.AlignCenter, d.get("status", ""))
            bar = QRect(thumb.left(), thumb.bottom() - 3, thumb.width(), 4)
            p.fillRect(bar, QColor(255, 255, 255, 40))
            w = int(bar.width() * max(pct, 0) / 100) if pct >= 0 else bar.width() // 4
            p.fillRect(QRect(bar.left(), bar.top(), w, 4), QColor(ACCENT))
        elif hovered or previewing:
            # bouton ▶ / ❚❚ d'aperçu au centre
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 120) if kind == "mi" else QColor(0, 0, 0, 150))
            p.drawEllipse(play)
            p.drawPixmap(play.center() - QPoint(11, 11) + QPoint(0 if playing else 1, 0),
                         svg_pixmap("pause" if playing else "play", "#ffffff", 22))
        p.restore()

        # badge en haut à gauche
        if kind in ("yt", "mi"):
            if d.get("files"):
                self._pill(p, thumb.x() + 6, thumb.y() + 6, "✓ Téléchargé", QColor(31, 107, 63, 225))
            else:
                self._pill(p, thumb.x() + 6, thumb.y() + 6, "YouTube" if kind == "yt" else "MyInstants",
                           QColor(0, 0, 0, 180))
        else:
            self._pill(p, thumb.x() + 6, thumb.y() + 6,
                       "Vidéo" if is_video_file(d["path"]) else "Son", QColor(0, 0, 0, 180))

        # durée en bas à droite
        dur = fmt_duration(d["video"].get("duration")) if kind == "yt" else d.get("dur", "")
        if dur and state != "downloading":
            fm = QFontMetrics(self.f_badge)
            self._pill(p, thumb.right() - 5, thumb.bottom() - fm.height() - 9, dur, QColor(0, 0, 0, 200),
                       right=True)

        # bouton en haut à droite : télécharger (YouTube / MyInstants) ou étoile (fichiers)
        if kind in ("yt", "mi") and state != "downloading" and not d.get("video", {}).get("live"):
            active = hovered or selected
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT) if active else QColor(0, 0, 0, 170))
            p.drawEllipse(btn)
            p.drawPixmap(btn.center() - QPoint(7, 7),
                         svg_pixmap("download", ACCENT_TEXT if active else "#ffffff", 16))
        elif kind == "file":
            fav = Path(d["path"]).name in self.win.settings.favorites
            if fav or hovered:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, 150))
                p.drawEllipse(btn)
                p.drawPixmap(btn.center() - QPoint(7, 7),
                             svg_pixmap("star", STAR if fav else "#ffffff", 16, STAR if fav else "none"))

        # titre + infos
        tr = QRect(card.x() + 10, thumb.bottom() + 8, card.width() - 20, 18)
        p.setFont(self.f_title)
        p.setPen(QColor(TEXT))
        p.drawText(tr, Qt.AlignHCenter | Qt.AlignVCenter,
                   QFontMetrics(self.f_title).elidedText(tile_title(d), Qt.ElideRight, tr.width()))
        mr = QRect(tr.x(), tr.bottom() + 3, tr.width(), 16)
        p.setFont(self.f_small)
        color, meta = MUTED, ""
        if kind in ("yt", "mi"):
            if state == "error":
                color, meta = RED, "✖ " + d.get("error", "Erreur")
            elif d.get("files") and state != "downloading":
                kinds = " + ".join({"video": "Vidéo", "wav": "WAV", "mp3": "MP3"}[m] for m in d["files"])
                color, meta = GREEN, f"{kinds} · glisse-moi sur la timeline"
            elif kind == "yt":
                v = d["video"]
                meta = " · ".join(x for x in (v.get("channel"), fmt_views(v.get("views"))) if x)
            else:
                meta = "▶ écouter · glisse-moi sur la timeline"
        else:
            meta = f"{Path(d['path']).suffix[1:].upper()} · {fmt_size(d.get('size', 0))}"
        p.setPen(QColor(color))
        p.drawText(mr, Qt.AlignHCenter | Qt.AlignVCenter,
                   QFontMetrics(self.f_small).elidedText(meta, Qt.ElideRight, mr.width()))
        p.restore()

    def editorEvent(self, event, model, option, index):
        t = event.type()
        if t in (event.Type.MouseButtonPress, event.Type.MouseButtonRelease, event.Type.MouseButtonDblClick) \
                and event.button() == Qt.LeftButton:
            d = tile_data(index)
            _, _, btn, play = self.geometry(option.rect)
            pos = event.position().toPoint()
            if d and d.get("state") != "downloading":
                if btn.contains(pos):
                    if t == event.Type.MouseButtonRelease:
                        self.button_clicked.emit(d, self.view.viewport().mapToGlobal(btn.bottomLeft() + QPoint(0, 4)))
                    return True
                in_play = play.contains(pos) or (d["kind"] == "mi" and QRect(play).adjusted(-10, -10, 10, 10).contains(pos))
                if in_play:
                    if t == event.Type.MouseButtonRelease:
                        self.play_clicked.emit(d)
                    return True
        return super().editorEvent(event, model, option, index)


class TileView(QListWidget):
    """Grille de vignettes ; les éléments téléchargés se glissent vers Resolve."""

    def __init__(self, win: "MainWindow", empty_text: str):
        super().__init__()
        self.win, self.empty_text = win, empty_text
        self.setViewMode(QListView.IconMode)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setGridSize(QSize(CARD_W, CARD_H))
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setFrameShape(QFrame.NoFrame)
        self.delegate = TileDelegate(win, self)
        self.setItemDelegate(self.delegate)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def startDrag(self, actions):
        paths, pm = [], None
        for it in self.selectedItems():
            d = tile_data(it)
            if d["kind"] == "mi" and not d.get("files"):
                self.win.download_instant_now(d)          # sons courts : téléchargés à la volée
            got = [p for p in self.win.paths_of(d) if p and Path(p).exists()]
            paths += got
            if got and pm is None:
                pm = self.win.thumb_for(d)
        if not paths:
            self.win.flash("Télécharge d'abord (bouton ⬇ sur la vignette), puis glisse-la sur la timeline.")
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(Path(p).resolve())) for p in paths])
        drag = QDrag(self)
        drag.setMimeData(mime)
        if pm and not pm.isNull():
            drag.setPixmap(pm.scaled(144, 81, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.setHotSpot(QPoint(72, 40))
        drag.exec(Qt.CopyAction)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0 and self.empty_text:
            p = QPainter(self.viewport())
            p.setPen(QColor(MUTED))
            p.drawText(self.viewport().rect().adjusted(40, 0, -40, 0), Qt.AlignCenter | Qt.TextWordWrap,
                       self.empty_text)


# --------------------------------------------------------------------------- #
#  Aperçu (lecteur intégré)                                                    #
# --------------------------------------------------------------------------- #
class ClickSlider(QSlider):
    """Curseur qui saute directement là où on clique."""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.maximum() > self.minimum():
            x = e.position().x()
            v = self.minimum() + (self.maximum() - self.minimum()) * x / max(1, self.width())
            self.setValue(int(v))
            self.sliderMoved.emit(int(v))
        super().mousePressEvent(e)


class PreviewPanel(QFrame):
    """Barre d'aperçu en bas : vidéo / pochette, lecture, position, volume, télécharger."""

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.setObjectName("preview")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(168)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(win.settings.preview_volume)
        self.player.setAudioOutput(self.audio)

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(16)
        self.media = QStackedWidget()
        self.media.setFixedSize(256, 144)
        self.video = QVideoWidget()
        self.video.setStyleSheet("background: black;")
        self.cover = QLabel()
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setStyleSheet("background: #101012; border-radius: 6px;")
        self.media.addWidget(self.cover)
        self.media.addWidget(self.video)
        self.player.setVideoOutput(self.video)
        h.addWidget(self.media)

        mid = QVBoxLayout()
        mid.setSpacing(6)
        self.title = QLabel()
        self.title.setObjectName("pvTitle")
        self.sub = QLabel()
        self.sub.setObjectName("pvSub")
        mid.addWidget(self.title)
        mid.addWidget(self.sub)
        mid.addStretch(1)
        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        self.play_btn = QToolButton()
        self.play_btn.setObjectName("round")
        self.play_btn.setIconSize(QSize(18, 18))
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.clicked.connect(self.toggle)
        self.pos = ClickSlider(Qt.Horizontal)
        self.pos.sliderMoved.connect(self.player.setPosition)
        self.time = QLabel("0:00 / 0:00")
        self.time.setObjectName("pvSub")
        self.time.setMinimumWidth(92)
        vol_ic = QLabel()
        vol_ic.setPixmap(svg_pixmap("volume", MUTED, 16))
        self.vol = ClickSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(int(win.settings.preview_volume * 100))
        self.vol.setFixedWidth(90)
        self.vol.valueChanged.connect(self._volume)
        ctl.addWidget(self.play_btn)
        ctl.addWidget(self.pos, 1)
        ctl.addWidget(self.time)
        ctl.addSpacing(6)
        ctl.addWidget(vol_ic)
        ctl.addWidget(self.vol)
        mid.addLayout(ctl)
        h.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(6)
        top = QHBoxLayout()
        top.addStretch(1)
        self.ext_btn = QToolButton()
        self.ext_btn.setObjectName("tb")
        self.ext_btn.setIcon(svg_icon("external", MUTED, 16))
        self.ext_btn.setToolTip("Ouvrir la page d'origine dans le navigateur")
        self.ext_btn.clicked.connect(self._open_page)
        close = QToolButton()
        close.setObjectName("tb")
        close.setIcon(svg_icon("close", MUTED, 16))
        close.setToolTip("Fermer l'aperçu (Échap)")
        close.clicked.connect(self.close_preview)
        top.addWidget(self.ext_btn)
        top.addWidget(close)
        right.addLayout(top)
        self.dl_buttons: dict[str, QPushButton] = {}
        for mode, label in (("video", "Vidéo 1080p"), ("wav", "Audio WAV"), ("mp3", "Audio MP3")):
            b = QPushButton(label)
            b.setObjectName("accent" if mode != "mp3" else "")
            b.setIcon(svg_icon("download", ACCENT_TEXT if mode != "mp3" else TEXT, 14))
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedWidth(150)
            b.clicked.connect(lambda _=False, m=mode: self._download(m))
            self.dl_buttons[mode] = b
            right.addWidget(b)
        right.addStretch(1)
        h.addLayout(right)

        self.d: dict | None = None
        self.player.positionChanged.connect(self._position)
        self.player.durationChanged.connect(lambda ms: self.pos.setRange(0, ms))
        self.player.playbackStateChanged.connect(self._state)
        self.player.errorOccurred.connect(self._error)
        self.player.mediaStatusChanged.connect(self._status)
        self._state()
        self.hide()

    # -- actions
    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlayingState

    def toggle(self):
        if self.is_playing():
            self.player.pause()
        elif self.player.source().isValid():
            if self.player.mediaStatus() == QMediaPlayer.EndOfMedia:
                self.player.setPosition(0)
            self.player.play()

    def start(self, d: dict, title: str, sub: str, cover: QPixmap | None):
        self.d = d
        self.player.stop()
        self.player.setSource(QUrl())
        self.title.setText(QFontMetrics(self.title.font()).elidedText(title, Qt.ElideRight, 560))
        self.title.setToolTip(title)
        self.sub.setText(sub)
        self.sub.setStyleSheet("")
        self.pos.setRange(0, 0)
        self.time.setText("0:00 / 0:00")
        self.set_cover(cover)
        kind = d["kind"]
        self.dl_buttons["video"].setVisible(kind == "yt")
        for m in ("wav", "mp3"):
            self.dl_buttons[m].setVisible(kind in ("yt", "mi"))
        self.ext_btn.setVisible(kind in ("yt", "mi"))
        self.show()

    def set_cover(self, pm: QPixmap | None):
        if pm and not pm.isNull():
            self.cover.setPixmap(pm.scaled(256, 144, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.cover.setPixmap(svg_pixmap("music", "#ffffff", 40, opacity=0.5))
        self.media.setCurrentWidget(self.cover)

    def play_url(self, url: QUrl, show_video: bool):
        self.media.setCurrentWidget(self.video if show_video else self.cover)
        self.player.setSource(url)
        self.player.play()

    def fail(self, msg: str):
        self.sub.setText("✖ " + msg)
        self.sub.setStyleSheet(f"color: {RED};")

    def close_preview(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.d = None
        self.win.preview_key = None
        self.hide()
        self.win.refresh_tiles()

    # -- callbacks
    def _volume(self, v):
        self.audio.setVolume(v / 100)
        self.win.settings.preview_volume = v / 100

    def _position(self, ms):
        if not self.pos.isSliderDown():
            self.pos.setValue(ms)
        total = self.player.duration()
        if 0 < total < 60000:                     # sons courts : dixièmes de seconde
            f = lambda x: f"{x / 1000:.1f}".replace(".", ",") + " s"
            self.time.setText(f"{f(ms)} / {f(total)}")
        else:
            self.time.setText(f"{fmt_duration(ms // 1000) or '0:00'} / {fmt_duration(total // 1000) or '0:00'}")

    def _state(self, *_):
        playing = self.is_playing()
        self.play_btn.setIcon(svg_icon("pause" if playing else "play", ACCENT_TEXT, 18))
        self.win.refresh_tiles()

    def _status(self, st):
        if st in (QMediaPlayer.LoadingMedia, QMediaPlayer.StalledMedia):
            if not self.sub.text().startswith("✖"):
                self.sub.setText(self.sub.property("base") or self.sub.text())
        if st == QMediaPlayer.EndOfMedia:
            self._state()

    def _error(self, err, msg=""):
        if err != QMediaPlayer.NoError:
            self.fail("Lecture impossible : " + (msg or self.player.errorString() or "format non pris en charge"))
            log_error(f"Aperçu : {self.player.errorString()}")

    def _open_page(self):
        if not self.d:
            return
        url = self.d["video"]["url"] if self.d["kind"] == "yt" else self.d["item"]["page_url"]
        QDesktopServices.openUrl(QUrl(url))

    def _download(self, mode):
        if self.d and self.d.get("state") != "downloading":
            self.win.start_download(self.d, mode)


# --------------------------------------------------------------------------- #
#  Barre latérale                                                              #
# --------------------------------------------------------------------------- #
class SideItem(QPushButton):
    def __init__(self, icon: str, text: str, indent: int = 0, count: bool = True):
        super().__init__()
        self.setObjectName("side")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.icon_name = icon
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12 + indent, 0, 12, 0)
        lay.setSpacing(10)
        self.ic = QLabel()
        self.ic.setPixmap(svg_pixmap(icon, MUTED, 16))
        self.lbl = QLabel(text)
        self.lbl.setObjectName("sideText")
        self.cnt = QLabel("")
        self.cnt.setObjectName("sideCount")
        self.cnt.setVisible(count)
        for w in (self.ic, self.lbl, self.cnt):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.ic)
        lay.addWidget(self.lbl, 1)
        lay.addWidget(self.cnt)
        self.setFixedHeight(32)
        self.toggled.connect(lambda on: self.ic.setPixmap(svg_pixmap(self.icon_name, TEXT if on else MUTED, 16)))

    def set_count(self, n):
        self.cnt.setText(str(n) if n else "")


# --------------------------------------------------------------------------- #
#  Réglages                                                                    #
# --------------------------------------------------------------------------- #
class SettingsDialog(QDialog):
    def __init__(self, win: "MainWindow"):
        super().__init__(win)
        self.win, s = win, win.settings
        self.setWindowTitle("Réglages")
        self.setMinimumWidth(680)
        self.resize(700, 760)
        win.settings_dialog = self
        self.finished.connect(lambda _: setattr(win, "settings_dialog", None))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("dlgInner")
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        v = QVBoxLayout(inner)
        v.setContentsMargins(20, 18, 20, 8)
        v.setSpacing(10)

        # --- yt-dlp en premier : c'est ce qu'il faut quand YouTube ne marche plus
        v.addWidget(self._h("yt-dlp : le moteur qui télécharge YouTube"))
        self.ver_lbl = self._hint(f"Version installée : <b>{ytdlp_installed_version()}</b> · "
                                  "dernière version : vérification…")
        v.addWidget(self.ver_lbl)
        row0 = QHBoxLayout()
        self.channel = QComboBox()
        self.channel.addItem("Stable (recommandé)", "stable")
        self.channel.addItem("Nightly (correctifs du jour)", "nightly")
        self.channel.setCurrentIndex(1 if s.ytdlp_channel == "nightly" else 0)
        self.channel.currentIndexChanged.connect(self._channel)
        self.upd_btn = QPushButton("Mettre à jour yt-dlp")
        self.upd_btn.setObjectName("accent")
        self.upd_btn.setIcon(svg_icon("download", ACCENT_TEXT, 14))
        self.upd_btn.setCursor(Qt.PointingHandCursor)
        self.upd_btn.clicked.connect(lambda: win.run_ytdlp_update())
        row0.addWidget(QLabel("Canal :"))
        row0.addWidget(self.channel, 1)
        row0.addWidget(self.upd_btn)
        v.addLayout(row0)
        self.upd_status = self._hint("")
        v.addWidget(self.upd_status)
        auto = QCheckBox("Mettre à jour yt-dlp automatiquement au démarrage (recommandé)")
        auto.setChecked(s.ytdlp_auto_update)
        auto.toggled.connect(self._auto)
        v.addWidget(auto)
        v.addWidget(self._hint(
            "YouTube change souvent son fonctionnement : quand les téléchargements ne marchent plus, "
            "clique sur <b>Mettre à jour yt-dlp</b> (10 à 30 s, puis la fenêtre redémarre toute seule et reprend ta recherche). Si c'est déjà à jour "
            "et que ça ne marche toujours pas, choisis <b>Nightly</b> : il reçoit les corrections le jour même."))
        logs = QPushButton("Ouvrir le journal d'erreurs")
        logs.clicked.connect(lambda: (core.LOG_FILE.touch(exist_ok=True),
                                      QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.LOG_FILE)))))
        v.addWidget(logs, 0, Qt.AlignLeft)
        v.addSpacing(6)

        v.addWidget(self._h("Dossier des téléchargements"))
        row = QHBoxLayout()
        self.dir_edit = QLineEdit(s.download_dir)
        self.dir_edit.setReadOnly(True)
        pick = QPushButton("Changer…")
        pick.clicked.connect(self._pick)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(pick)
        v.addLayout(row)

        top = QCheckBox("Garder la fenêtre au-dessus de DaVinci Resolve (pratique pour glisser-déposer)")
        top.setChecked(s.always_on_top)
        top.toggled.connect(win.set_on_top)
        v.addWidget(top)

        v.addSpacing(6)
        v.addWidget(self._h("Vitesse de téléchargement"))
        row3 = QHBoxLayout()
        fast = QCheckBox("Téléchargement rapide : plusieurs connexions en parallèle")
        fast.setChecked(s.fast_download)
        fast.toggled.connect(self._fast)
        self.conn = QComboBox()
        for n in (4, 8, 12, 16):
            self.conn.addItem(f"{n} connexions", n)
        self.conn.setCurrentIndex(max(0, [4, 8, 12, 16].index(s.connections) if s.connections in (4, 8, 12, 16) else 1))
        self.conn.currentIndexChanged.connect(self._conn)
        row3.addWidget(fast, 1)
        row3.addWidget(self.conn)
        v.addLayout(row3)
        v.addWidget(self._hint(
            "La vidéo et le son sont récupérés en même temps, en morceaux, puis assemblés <b>sans ré-encodage</b> : "
            "la qualité est strictement celle de YouTube. Si une vidéo doit être convertie en H.264, la carte "
            "graphique est utilisée quand c'est possible (NVIDIA, Intel, AMD). En cas de souci, l'application "
            "repasse toute seule en mode classique."))

        v.addSpacing(6)
        v.addWidget(self._h("MyInstants"))
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Pays des tendances :"))
        self.region = QComboBox()
        for code, label in MI_REGIONS:
            self.region.addItem(label, code)
        self.region.setCurrentIndex(next((i for i, (c, _) in enumerate(MI_REGIONS) if c == s.mi_region), 0))
        self.region.currentIndexChanged.connect(self._region)
        row4.addWidget(self.region, 1)
        v.addLayout(row4)

        v.addSpacing(6)
        v.addWidget(self._h("Si YouTube bloque (« confirme que tu n'es pas un robot »)"))
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Utiliser ma session YouTube de :"))
        self.cookie = QComboBox()
        browsers = [("", "Aucun (par défaut)"), ("firefox", "Firefox (conseillé)"), ("edge", "Microsoft Edge"),
                    ("chrome", "Google Chrome"), ("brave", "Brave"), ("opera", "Opera")]
        for k, label in browsers:
            self.cookie.addItem(label, k)
        self.cookie.setCurrentIndex(next((i for i, (k, _) in enumerate(browsers) if k == s.cookies_browser), 0))
        self.cookie.currentIndexChanged.connect(self._cookies)
        row2.addWidget(self.cookie, 1)
        v.addLayout(row2)
        v.addWidget(self._hint("Avec Chrome / Edge / Brave, ferme complètement le navigateur avant de télécharger "
                               "(Windows verrouille ses cookies). Firefox n'a pas ce problème."))

        v.addSpacing(6)
        v.addWidget(self._h("Application"))
        v.addWidget(self._hint(
            f"Installée dans : <b>{ROOT}</b><br>"
            f"ffmpeg {'✔' if ffmpeg_path() else '✖'} · Deno {'✔' if deno_path() else '✖'}<br>"
            "Ne télécharge que des contenus que tu as le droit d'utiliser (libres de droits, Creative Commons, "
            "ou avec l'accord de l'auteur)."))
        v.addStretch(1)
        close = QPushButton("Fermer")
        close.setObjectName("accent")
        close.clicked.connect(self.accept)
        crow = QHBoxLayout()
        crow.setContentsMargins(20, 0, 20, 0)
        crow.addStretch(1)
        crow.addWidget(close)
        outer.addLayout(crow)
        self.refresh_versions()
        self.set_updating(win.updating)

    # --- yt-dlp
    def refresh_versions(self):
        def done(latest):
            if self.win.settings_dialog is not self:
                return
            inst = ytdlp_installed_version()
            ch = self.win.settings.ytdlp_channel
            target = latest["nightly" if ch == "nightly" else "stable"]
            ok = core._vtuple(inst) >= core._vtuple(target)
            self.ver_lbl.setText(
                f"Version installée : <b>{inst}</b> · dernière {'nightly' if ch == 'nightly' else 'stable'} : "
                f"<b>{target}</b> " + (f"<span style='color:{GREEN}'>✔ à jour</span>" if ok
                                       else f"<span style='color:{STAR}'>⬆ mise à jour disponible</span>"))

        def fail(msg):
            if self.win.settings_dialog is self:
                self.ver_lbl.setText(f"Version installée : <b>{ytdlp_installed_version()}</b> · "
                                     "impossible de vérifier la dernière version (connexion ?)")
        self.win.run_task(ytdlp_latest_versions, on_done=done, on_fail=fail)

    def set_updating(self, on: bool, text: str = ""):
        self.upd_btn.setEnabled(not on)
        self.upd_btn.setText("Mise à jour en cours…" if on else "Mettre à jour yt-dlp")
        self.channel.setEnabled(not on)
        if text:
            self.upd_status.setText(text)

    def _channel(self, i):
        self.win.settings.ytdlp_channel = self.channel.itemData(i)
        self.win.settings.save()
        self.refresh_versions()

    def _auto(self, on):
        self.win.settings.ytdlp_auto_update = on
        self.win.settings.save()

    @staticmethod
    def _h(t):
        lbl = QLabel(t)
        lbl.setObjectName("h")
        return lbl

    @staticmethod
    def _hint(t):
        lbl = QLabel(t)
        lbl.setObjectName("hint")
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        return lbl

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier des téléchargements", self.win.settings.download_dir)
        if d:
            self.dir_edit.setText(d)
            self.win.set_download_dir(d)

    def _cookies(self, i):
        self.win.settings.cookies_browser = self.cookie.itemData(i) or ""
        self.win.settings.save()

    def _fast(self, on):
        self.win.settings.fast_download = on
        self.win.settings.save()

    def _conn(self, i):
        self.win.settings.connections = self.conn.itemData(i)
        self.win.settings.save()

    def _region(self, i):
        self.win.settings.mi_region = self.region.itemData(i)
        self.win.settings.save()
        if self.win.view == "mi" and not self.win.mi_query:
            self.win.mi_reload()


# --------------------------------------------------------------------------- #
#  Fenêtre principale                                                          #
# --------------------------------------------------------------------------- #
STYLE = f"""
* {{ font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QWidget#central, QDialog {{ background: {BG}; }}
QWidget#topbar {{ background: {PANEL}; border-bottom: 1px solid {LINE}; }}
QWidget#sidebar {{ background: {PANEL}; border-right: 1px solid {LINE}; }}
QWidget#main {{ background: {BG}; }}
QFrame#preview {{ background: {PANEL}; border-top: 1px solid {LINE}; }}
QFrame#banner {{ background: #2a2a1c; border: 1px solid #4b5222; border-radius: 8px; }}
QLabel#bannerText {{ color: #e9edd2; }}
QWidget#dlgInner {{ background: {BG}; }}
QLabel#pvTitle {{ font-size: 15px; font-weight: 600; color: #ffffff; }}
QLabel#pvSub {{ color: {MUTED}; font-size: 12px; }}
QToolButton#round {{ background: {ACCENT}; border: 0; border-radius: 20px; }}
QToolButton#round:hover {{ background: #d3ff55; }}
QSlider::groove:horizontal {{ height: 4px; background: #34343a; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #ffffff; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
QLineEdit {{ background: #232327; border: 1px solid transparent; border-radius: 7px; padding: 7px 10px; }}
QLineEdit:focus {{ border-color: #3d3d44; background: #26262b; }}
QLineEdit#search {{ padding-left: 4px; }}
QToolButton#tb {{ background: transparent; border: 0; border-radius: 6px; padding: 5px; }}
QToolButton#tb:hover {{ background: #2a2a2f; }}
QPushButton {{ background: #26262b; border: 1px solid #323238; border-radius: 7px; padding: 7px 14px; }}
QPushButton:hover {{ background: #2e2e34; }}
QPushButton#accent {{ background: {ACCENT}; color: {ACCENT_TEXT}; border: 0; font-weight: 600; padding: 7px 16px; }}
QPushButton#accent:hover {{ background: #d3ff55; }}
QPushButton#accent:disabled {{ background: #4f5a26; color: #22251a; }}
QWidget#pills {{ background: #232327; border-radius: 9px; }}
QPushButton#pill {{ background: transparent; border: 0; color: {MUTED}; padding: 6px 16px; border-radius: 7px; }}
QPushButton#pill:hover {{ color: {TEXT}; }}
QPushButton#pill:checked {{ background: #393940; color: #ffffff; font-weight: 600; }}
QPushButton#side {{ background: transparent; border: 0; border-radius: 7px; text-align: left; padding: 0; }}
QPushButton#side:hover {{ background: #232327; }}
QPushButton#side:checked {{ background: #2a2a30; }}
QLabel#sideText {{ color: #c9c9ce; }}
QLabel#sideCount {{ color: {MUTED}; font-size: 12px; }}
QLabel#sideHead {{ color: #c9c9ce; }}
QLabel#title {{ font-size: 19px; font-weight: 600; color: #ffffff; }}
QLabel#count {{ color: {MUTED}; font-size: 12px; padding-bottom: 2px; }}
QLabel#flash {{ color: {MUTED}; font-size: 12px; }}
QLabel#h {{ font-weight: 600; color: #ffffff; }}
QLabel#hint {{ color: {MUTED}; font-size: 12px; }}
QComboBox {{ background: #232327; border: 1px solid #323238; border-radius: 7px; padding: 6px 10px; min-width: 140px; }}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QComboBox QAbstractItemView {{ background: #232327; border: 1px solid #323238; selection-background-color: #393940; outline: 0; }}
QListWidget {{ background: {BG}; border: 0; outline: 0; }}
QMenu {{ background: #232327; border: 1px solid #34343a; padding: 5px; }}
QMenu::item {{ padding: 7px 22px 7px 10px; border-radius: 5px; }}
QMenu::item:selected {{ background: #393940; }}
QMenu::separator {{ height: 1px; background: #34343a; margin: 4px 6px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #38383e; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QToolTip {{ background: #232327; color: {TEXT}; border: 1px solid #34343a; padding: 4px; }}
"""

MI_MODES = {"wav": MODES["wav"], "mp3": ("Audio MP3 (original)", "Le fichier d'origine de MyInstants")}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        global _WIN
        _WIN = self
        self.settings = Settings()
        Path(self.settings.download_dir).mkdir(parents=True, exist_ok=True)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(6)
        self.net = QNetworkAccessManager(self)
        self.relay = StreamRelay()
        # Tâches de fond : un seul pont, des callbacks rangés par numéro de tâche.
        self.bridge = Bridge(self)
        self.bridge.done.connect(self._task_done, Qt.QueuedConnection)
        self.bridge.failed.connect(self._task_failed, Qt.QueuedConnection)
        self.bridge.progress.connect(self._task_progress, Qt.QueuedConnection)
        self.tasks: dict[int, tuple] = {}
        self.next_task = 0

        self.yt_thumbs: dict[str, QPixmap] = {}       # id vidéo -> miniature
        self.file_thumbs: dict[str, QPixmap] = {}     # chemin -> miniature
        self.thumb_jobs: set[str] = set()
        self.videos: dict[str, dict] = {}             # YouTube : id -> état (gardé entre les recherches)
        self.instants: dict[str, dict] = {}           # MyInstants : id -> état
        self.result_ids: list[str] = []
        self.query, self.count, self.loading, self.has_more = "", PAGE_SIZE, False, False
        self.search_token = 0
        self.mi_ids: list[str] = []
        self.mi_source, self.mi_query, self.mi_page = "trending", "", 1
        self.mi_loading, self.mi_has_more, self.mi_token = False, False, 0
        self.preview_key: str | None = None
        self.preview_token = 0
        self.preview_cache: dict[str, dict] = {}
        self.active = 0
        self.updating = False                         # mise à jour de yt-dlp en cours
        self.settings_dialog = None
        self.view = "yt"                              # "yt" | "mi" | "all" | "fav"

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1180, 780)

        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_main(), 1)
        self.preview = PreviewPanel(self)
        right.addWidget(self.preview)
        body.addLayout(right, 1)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

        self._refresh_timer = QTimer(self, singleShot=True)
        self._refresh_timer.timeout.connect(self.refresh_library)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda _: self._refresh_timer.start(400))
        self._watch_dir()

        sc = QShortcut(QKeySequence(Qt.Key_Space), self)
        sc.activated.connect(self._space)
        QShortcut(QKeySequence(Qt.Key_Escape), self).activated.connect(
            lambda: self.preview.isVisible() and self.preview.close_preview())

        self.set_on_top(self.settings.always_on_top, save=False)
        self.show_view("yt")
        self.refresh_library()
        self.search.setFocus()
        QTimer.singleShot(2500, self._auto_check_ytdlp)

    # ------------------------------------------------------------------ UI
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setAttribute(Qt.WA_StyledBackground)
        bar.setFixedHeight(56)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 0, 16, 0)
        h.setSpacing(6)
        for icon, tip, fn in (("menu", "Afficher / masquer le panneau",
                               lambda: self.sidebar.setVisible(not self.sidebar.isVisible())),
                              ("gear", "Réglages", lambda: SettingsDialog(self).exec())):
            b = QToolButton()
            b.setObjectName("tb")
            b.setIcon(svg_icon(icon, TEXT, 20))
            b.setIconSize(QSize(20, 20))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.addAction(svg_icon("search", MUTED, 16), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(380)
        self.search.returnPressed.connect(self.new_search)
        h.addWidget(self.search)
        h.addStretch(1)

        self.pills = QWidget()
        self.pills.setObjectName("pills")
        self.pills.setAttribute(Qt.WA_StyledBackground)
        ph = QHBoxLayout(self.pills)
        ph.setContentsMargins(3, 3, 3, 3)
        ph.setSpacing(2)
        self.pill_group = QButtonGroup(self)
        for i, t in enumerate(("Tout", "Vidéos", "Sons")):
            b = QPushButton(t)
            b.setObjectName("pill")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.pill_group.addButton(b, i)
            ph.addWidget(b)
        self.pill_group.button(0).setChecked(True)
        self.pill_group.idClicked.connect(lambda _: self.refresh_library())
        self.pills.setFixedHeight(38)
        h.addWidget(self.pills, 0, Qt.AlignVCenter)
        return bar

    def _build_sidebar(self) -> QWidget:
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setAttribute(Qt.WA_StyledBackground)
        self.sidebar.setFixedWidth(232)
        v = QVBoxLayout(self.sidebar)
        v.setContentsMargins(10, 12, 10, 12)
        v.setSpacing(2)
        self.side_group = QButtonGroup(self)
        self.side_yt = SideItem("youtube", "Recherche YouTube")
        self.side_mi = SideItem("button", "MyInstants")
        self.side_fav = SideItem("star", "Favoris")
        self.side_all = SideItem("layers", "Téléchargements")
        for b, key in ((self.side_yt, "yt"), (self.side_mi, "mi"), (self.side_fav, "fav"), (self.side_all, "all")):
            self.side_group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.show_view(k))
            v.addWidget(b)
        v.addSpacing(18)

        head = QHBoxLayout()
        head.setContentsMargins(12, 0, 4, 0)
        ic = QLabel()
        ic.setPixmap(svg_pixmap("clock", MUTED, 16))
        t = QLabel("Recherches récentes")
        t.setObjectName("sideHead")
        clear = QToolButton()
        clear.setObjectName("tb")
        clear.setIcon(svg_icon("trash", MUTED, 14))
        clear.setToolTip("Effacer l'historique")
        clear.clicked.connect(self._clear_history)
        head.addWidget(ic)
        head.addSpacing(4)
        head.addWidget(t, 1)
        head.addWidget(clear)
        v.addLayout(head)
        self.history_box = QVBoxLayout()
        self.history_box.setSpacing(2)
        v.addLayout(self.history_box)
        v.addStretch(1)

        folder = SideItem("folder", "Ouvrir le dossier", count=False)
        folder.setCheckable(False)
        folder.clicked.connect(self.open_folder)
        v.addWidget(folder)
        self._fill_history()
        return self.sidebar

    def _build_main(self) -> QWidget:
        main = QWidget()
        main.setObjectName("main")
        v = QVBoxLayout(main)
        v.setContentsMargins(24, 18, 18, 8)
        v.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(10)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.title.setMaximumWidth(520)
        self.count_lbl = QLabel()
        self.count_lbl.setObjectName("count")
        self.action_btn = QPushButton()
        self.action_btn.setObjectName("accent")
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._action)
        self.sort = QComboBox()
        self.sort.setMaxVisibleItems(20)
        self.sort.currentIndexChanged.connect(self._resort)
        head.addWidget(self.title)
        head.addWidget(self.count_lbl, 0, Qt.AlignBottom)
        head.addStretch(1)
        head.addWidget(self.action_btn)
        head.addWidget(self.sort)
        v.addLayout(head)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        self.banner.setAttribute(Qt.WA_StyledBackground)
        bh = QHBoxLayout(self.banner)
        bh.setContentsMargins(14, 8, 8, 8)
        self.banner_lbl = QLabel()
        self.banner_lbl.setObjectName("bannerText")
        self.banner_lbl.setWordWrap(True)
        self.banner_btn = QPushButton("Mettre à jour yt-dlp")
        self.banner_btn.setObjectName("accent")
        self.banner_btn.setCursor(Qt.PointingHandCursor)
        self.banner_btn.clicked.connect(lambda: self.run_ytdlp_update())
        bclose = QToolButton()
        bclose.setObjectName("tb")
        bclose.setIcon(svg_icon("close", MUTED, 14))
        bclose.clicked.connect(self.banner.hide)
        bh.addWidget(self.banner_lbl, 1)
        bh.addWidget(self.banner_btn)
        bh.addWidget(bclose)
        self.banner.hide()
        v.addWidget(self.banner)

        self.stack = QStackedWidget()
        self.yt_view = TileView(self, "Tape une recherche en haut (ex. « whoosh sound effect ») puis Entrée.\n\n"
                                      "▶ au centre d'une vignette : aperçu.   ⬇ en haut à droite : télécharger.\n"
                                      "Ensuite, glisse la vignette sur ta timeline Resolve.")
        self.mi_view = TileView(self, "Chargement des sons MyInstants…")
        self.lib_view = TileView(self, "Aucun fichier pour l'instant.\nTélécharge depuis « Recherche YouTube » "
                                       "ou « MyInstants ».")
        for view in (self.yt_view, self.mi_view, self.lib_view):
            view.delegate.button_clicked.connect(self._tile_button)
            view.delegate.play_clicked.connect(self.open_preview)
            view.itemDoubleClicked.connect(self._double_click)
            view.customContextMenuRequested.connect(lambda pos, vw=view: self._context_menu(vw, pos))
            view.itemSelectionChanged.connect(self._update_action)
            self.stack.addWidget(view)
        self.yt_view.verticalScrollBar().valueChanged.connect(self._maybe_load_more)
        self.mi_view.verticalScrollBar().valueChanged.connect(self._mi_maybe_more)
        v.addWidget(self.stack, 1)
        self.flash_lbl = QLabel("")
        self.flash_lbl.setObjectName("flash")
        v.addWidget(self.flash_lbl)
        return main

    def refresh_tiles(self):
        for view in (self.yt_view, self.mi_view, self.lib_view):
            view.viewport().update()

    # ------------------------------------------------------- tâches de fond
    def run_task(self, fn, *args, on_done=None, on_fail=None, on_progress=None):
        self.next_task += 1
        tid = self.next_task
        task = Task(tid, self.bridge, fn, *args, with_progress=on_progress is not None)
        self.tasks[tid] = (task, on_done, on_fail, on_progress)   # garde la tâche en vie
        self.pool.start(task)
        return tid

    def _task_done(self, tid, result):
        _, on_done, _, _ = self.tasks.pop(tid, (None, None, None, None))
        if on_done:
            self._safe(on_done, result)

    def _task_failed(self, tid, msg):
        _, _, on_fail, _ = self.tasks.pop(tid, (None, None, None, None))
        if on_fail:
            self._safe(on_fail, msg)

    def _task_progress(self, tid, pct, text):
        entry = self.tasks.get(tid)
        if entry and entry[3]:
            self._safe(entry[3], pct, text)

    def _safe(self, fn, *args):
        try:
            fn(*args)
        except Exception:
            import traceback
            log_error(traceback.format_exc())
            traceback.print_exc()

    # ------------------------------------------------------------- vues
    def show_view(self, key: str):
        self.view = key
        {"yt": self.side_yt, "mi": self.side_mi, "fav": self.side_fav, "all": self.side_all}[key].setChecked(True)
        self.sort.blockSignals(True)
        self.sort.clear()
        if key == "yt":
            self.sort.addItems(["Pertinence", "Plus de vues", "Plus courtes", "Plus longues"])
            self.stack.setCurrentWidget(self.yt_view)
            self.search.setPlaceholderText("Rechercher sur YouTube…  (ou colle un lien)")
            self.search.setText(self.query)
        elif key == "mi":
            for k, label in MI_LISTS:
                self.sort.addItem(label, k)
            self.sort.setCurrentIndex(next((i for i, (k, _) in enumerate(MI_LISTS) if k == self.mi_source), 0))
            self.stack.setCurrentWidget(self.mi_view)
            self.search.setPlaceholderText("Rechercher un son sur MyInstants…  (ex. vine boom, bruh)")
            self.search.setText(self.mi_query)
            if not self.mi_ids and not self.mi_loading:
                self.mi_reload()
        else:
            self.sort.addItems(["Plus récents", "Nom (A → Z)", "Taille"])
            self.stack.setCurrentWidget(self.lib_view)
            self.search.setPlaceholderText("Rechercher sur YouTube…  (ou colle un lien)")
        self.sort.blockSignals(False)
        self.pills.setVisible(key in ("all", "fav"))
        if key in ("all", "fav"):
            self.refresh_library()
        self._update_header()

    def _update_header(self):
        fm = QFontMetrics(self.title.font())
        if self.view == "yt":
            title = f"« {self.query} »" if self.query else "Recherche YouTube"
            n = len(self.result_ids)
            self.count_lbl.setText(("Recherche…" if self.loading and not n else f"{n} vidéos") if self.query else "")
        elif self.view == "mi":
            label = dict(MI_LISTS).get(self.mi_source, "")
            title = f"« {self.mi_query} »" if self.mi_query else f"MyInstants · {label}"
            n = len(self.mi_ids)
            self.count_lbl.setText("Chargement…" if self.mi_loading and not n else f"{n} sons")
        else:
            title = "Favoris" if self.view == "fav" else "Téléchargements"
            self.count_lbl.setText(f"{self.lib_view.count()} fichiers")
        self.title.setText(fm.elidedText(title, Qt.ElideRight, 500))
        self._update_action()

    def current_view(self) -> TileView:
        return {"yt": self.yt_view, "mi": self.mi_view}.get(self.view, self.lib_view)

    def _update_action(self):
        if self.view in ("yt", "mi"):
            n = len(self.current_view().selectedItems())
            self.action_btn.setIcon(svg_icon("download", ACCENT_TEXT, 16))
            self.action_btn.setText(f"Télécharger ({n})" if n > 1 else "Télécharger")
            self.action_btn.setEnabled(n > 0)
            self.action_btn.setToolTip("Sélectionne une ou plusieurs vignettes (Ctrl / Maj + clic)")
        else:
            self.action_btn.setIcon(svg_icon("folder", ACCENT_TEXT, 16))
            self.action_btn.setText("Ouvrir le dossier")
            self.action_btn.setEnabled(True)
            self.action_btn.setToolTip(self.settings.download_dir)

    def _action(self):
        if self.view in ("yt", "mi"):
            sel = [tile_data(it) for it in self.current_view().selectedItems()]
            if sel:
                self._download_menu(sel, self.action_btn.mapToGlobal(QPoint(0, self.action_btn.height() + 4)))
        else:
            self.open_folder()

    def flash(self, text: str, ms: int = 6000):
        self.flash_lbl.setText(text)
        QTimer.singleShot(ms, lambda t=text: self.flash_lbl.text() == t and self.flash_lbl.setText(""))

    def _space(self):
        if self.search.hasFocus():
            self.search.insert(" ")
        elif self.preview.isVisible():
            self.preview.toggle()

    # ------------------------------------------------------------ recherche
    def new_search(self, query: str | None = None, source: str | None = None):
        q = (query if isinstance(query, str) else self.search.text()).strip()
        src = source or ("mi" if self.view == "mi" else "yt")
        if src == "yt" and self.updating:
            self.flash("Mise à jour de yt-dlp en cours… réessaie dans quelques secondes.")
            return
        if src == "mi":
            self.mi_search(q)
            return
        if not q:
            return
        self.query, self.count, self.has_more = q, PAGE_SIZE, False
        self.result_ids = []
        self.loading = False
        self.search_token += 1          # les réponses des recherches précédentes seront ignorées
        self.yt_view.clear()
        self.yt_view.empty_text = "Recherche en cours…"
        self._add_history(q)
        self.show_view("yt")
        self._run_search()

    def _run_search(self):
        if self.loading:
            return
        self.loading = True
        self._update_header()
        self.flash("Recherche en cours…", 30000)
        token, query = self.search_token, self.query
        self.run_task(search_youtube, query, self.count, self.settings,
                      on_done=lambda res: self._on_results(token, query, res),
                      on_fail=lambda msg: self._on_search_failed(token, msg))

    def _on_results(self, token, query, results):
        if token != self.search_token:
            return
        self.loading = False
        new = 0
        for v in results:
            if v["id"] in self.result_ids:
                continue
            new += 1
            st = self.videos.setdefault(v["id"], {"kind": "yt", "video": v, "files": {}, "state": ""})
            st["video"] = v
            self.result_ids.append(v["id"])
            self._load_yt_thumb(v["id"])
        self.has_more = bool(new) and not is_url(query) and len(self.result_ids) < 300
        self._resort()
        self.flash("")
        if not self.result_ids:
            self.yt_view.empty_text = f"Aucun résultat pour « {query} »."
            self.yt_view.viewport().update()
        self.side_yt.set_count(len(self.result_ids))
        QTimer.singleShot(50, self._maybe_load_more)   # si tout tient à l'écran, on en charge plus

    def _on_search_failed(self, token, msg):
        if token != self.search_token:
            return
        self.loading = False
        self.has_more = False
        self._update_header()
        self.flash("Erreur de recherche : " + msg, 30000)
        if not self.result_ids:
            self.yt_view.empty_text = ("La recherche a échoué :\n" + msg +
                                       "\n\nVérifie ta connexion, puis réessaie (Entrée).")
            self.yt_view.viewport().update()

    def _maybe_load_more(self, *_):
        sb = self.yt_view.verticalScrollBar()
        if self.has_more and not self.loading and self.view == "yt" and sb.value() >= sb.maximum() - 150:
            self.count += PAGE_SIZE
            self._run_search()

    def _resort(self, *_):
        if self.view == "mi":
            k = self.sort.currentData()
            if k and (k != self.mi_source or self.mi_query):
                self.mi_source, self.mi_query = k, ""
                self.search.clear()
                self.mi_reload()
            return
        if self.view != "yt":
            self.refresh_library()
            return
        ids = list(self.result_ids)
        mode = self.sort.currentIndex()
        if mode == 1:
            ids.sort(key=lambda i: -(self.videos[i]["video"].get("views") or 0))
        elif mode == 2:
            ids.sort(key=lambda i: self.videos[i]["video"].get("duration") or 10 ** 9)
        elif mode == 3:
            ids.sort(key=lambda i: -(self.videos[i]["video"].get("duration") or 0))
        sel = {tile_data(it)["video"]["id"] for it in self.yt_view.selectedItems()}
        pos = self.yt_view.verticalScrollBar().value()
        self.yt_view.clear()
        for i in ids:
            it = QListWidgetItem()
            it.setData(ROLE, {"kind": "yt", "id": i})
            it.setSizeHint(QSize(CARD_W, CARD_H))
            it.setToolTip(self.videos[i]["video"]["title"])
            self.yt_view.addItem(it)
            it.setSelected(i in sel)
        self.yt_view.verticalScrollBar().setValue(pos)
        self._update_header()

    def _load_yt_thumb(self, vid: str):
        if vid in self.yt_thumbs:
            return
        reply = self.net.get(QNetworkRequest(QUrl(f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg")))

        def done():
            if reply.error() == QNetworkReply.NoError:
                pm = QPixmap()
                if pm.loadFromData(reply.readAll()):
                    self.yt_thumbs[vid] = pm
                    self.yt_view.viewport().update()
                    if self.preview_key == "yt:" + vid and self.preview.media.currentWidget() is self.preview.cover:
                        self.preview.set_cover(pm)
            reply.deleteLater()
        reply.finished.connect(done)

    # ------------------------------------------------------------ MyInstants
    def mi_search(self, q: str):
        self.mi_query = q
        if q:
            self._add_history("mi:" + q)
        if self.view != "mi":
            self.show_view("mi")
        self.mi_reload()

    def mi_reload(self):
        self.mi_token += 1
        self.mi_ids, self.mi_page, self.mi_has_more, self.mi_loading = [], 1, False, False
        self.mi_view.clear()
        self.mi_view.empty_text = "Chargement des sons MyInstants…"
        self._mi_fetch()

    def _mi_fetch(self):
        if self.mi_loading:
            return
        self.mi_loading = True
        self._update_header()
        token, page = self.mi_token, self.mi_page
        self.run_task(myinstants_list, self.mi_source, self.mi_query, page, self.settings.mi_region,
                      on_done=lambda res: self._mi_results(token, res),
                      on_fail=lambda msg: self._mi_failed(token, msg))

    def _mi_results(self, token, items):
        if token != self.mi_token:
            return
        self.mi_loading = False
        new = 0
        for item in items:
            if item["id"] in self.mi_ids:
                continue
            new += 1
            st = self.instants.setdefault(item["id"], {"kind": "mi", "item": item, "files": {}, "state": ""})
            st["item"] = item
            self.mi_ids.append(item["id"])
            it = QListWidgetItem()
            it.setData(ROLE, {"kind": "mi", "id": item["id"]})
            it.setSizeHint(QSize(CARD_W, CARD_H))
            it.setToolTip(item["title"])
            self.mi_view.addItem(it)
        self.mi_has_more = len(items) >= MI_PAGE and new > 0 and self.mi_page < 40
        self.mi_page += 1
        if not self.mi_ids:
            self.mi_view.empty_text = (f"Aucun son pour « {self.mi_query} »." if self.mi_query
                                       else "Aucun son dans cette liste.")
        self.side_mi.set_count(len(self.mi_ids))
        self._update_header()
        QTimer.singleShot(50, self._mi_maybe_more)

    def _mi_failed(self, token, msg):
        if token != self.mi_token:
            return
        self.mi_loading = False
        self.mi_has_more = False
        self._update_header()
        self.flash("MyInstants : " + msg, 20000)
        if not self.mi_ids:
            self.mi_view.empty_text = "MyInstants ne répond pas :\n" + msg + "\n\nRéessaie dans un instant."
            self.mi_view.viewport().update()

    def _mi_maybe_more(self, *_):
        sb = self.mi_view.verticalScrollBar()
        if self.mi_has_more and not self.mi_loading and self.view == "mi" and sb.value() >= sb.maximum() - 150:
            self._mi_fetch()

    def download_instant_now(self, d: dict):
        """Pour glisser un son MyInstants pas encore téléchargé : on le récupère tout de suite (WAV)."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            path = myinstants_download(d["item"], "wav", self.settings)
            d["files"]["wav"] = path
            d["state"] = "done"
            self._save_thumb(d, path)
            self.refresh_tiles()
        except Exception as e:  # noqa: BLE001
            self.flash("✖ " + core.friendly_error(e), 15000)
        finally:
            QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------ aperçu
    def open_preview(self, d: dict):
        key = tile_key(d)
        if key == self.preview_key and self.preview.isVisible() and self.preview.player.source().isValid():
            self.preview.toggle()
            return
        self.preview_key = key
        self.preview_token += 1
        token = self.preview_token
        kind = d["kind"]
        if kind == "mi":
            item = d["item"]
            self.preview.start(d, item["title"], "MyInstants · aperçu", instant_cover(item["color"]))
            src = d["files"].get("wav") or d["files"].get("mp3")
            url = QUrl.fromLocalFile(src) if src and Path(src).exists() else QUrl(self.relay.local_url(item["mp3"]))
            self.preview.play_url(url, False)
        elif kind == "file":
            path = d["path"]
            vid = is_video_file(path)
            self.preview.start(d, Path(path).stem, ("Vidéo" if vid else "Son") + " · fichier téléchargé",
                               self.thumb_for(d))
            self.preview.play_url(QUrl.fromLocalFile(path), vid)
        else:
            v = d["video"]
            self.preview.start(d, v["title"], "Chargement de l'aperçu…", self.yt_thumbs.get(v["id"]))
            cached = self.preview_cache.get(v["id"])
            if cached:
                self._preview_ready(token, d, cached)
            else:
                self.run_task(preview_stream, v, self.settings,
                              on_done=lambda info: self._preview_ready(token, d, info),
                              on_fail=lambda msg: token == self.preview_token and self.preview.fail(msg))
        self.refresh_tiles()

    def _preview_ready(self, token, d, info):
        if token != self.preview_token:
            return
        self.preview_cache[d["video"]["id"]] = info
        v = d["video"]
        sub = " · ".join(x for x in (v.get("channel"), "Aperçu 360p" if info["has_video"] else "Aperçu audio") if x)
        self.preview.sub.setText(sub)
        self.preview.play_url(QUrl(self.relay.local_url(info["url"])), info["has_video"])

    # ------------------------------------------------------ historique
    def _add_history(self, q: str):
        if is_url(q):
            return
        h = [x for x in self.settings.history if x.lower() != q.lower()]
        self.settings.history = ([q] + h)[:12]
        self.settings.save()
        self._fill_history()

    def _clear_history(self):
        self.settings.history = []
        self.settings.save()
        self._fill_history()

    def _fill_history(self):
        while self.history_box.count():
            w = self.history_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        for q in self.settings.history:
            mi = q.startswith("mi:")
            text = q[3:] if mi else q
            b = SideItem("button" if mi else "search", text, indent=14, count=False)
            b.setCheckable(False)
            b.setToolTip(("MyInstants : " if mi else "YouTube : ") + text)
            b.clicked.connect(lambda _=False, t=text, m=mi: self.new_search(t, "mi" if m else "yt"))
            self.history_box.addWidget(b)

    # ---------------------------------------------------- téléchargement
    def _tile_button(self, d: dict, gpos: QPoint):
        if d["kind"] in ("yt", "mi"):
            self._download_menu([d], gpos)
        else:
            self.toggle_favorite(d["path"])

    def toggle_favorite(self, path: str):
        name = Path(path).name
        fav = self.settings.favorites
        if name in fav:
            fav.remove(name)
        else:
            fav.append(name)
        self.settings.save()
        if self.view == "fav":
            self.refresh_library()
        else:
            self.lib_view.viewport().update()
            self.side_fav.set_count(len(self._lib_files(fav_only=True)))

    def _download_menu(self, items: list[dict], gpos: QPoint):
        items = [d for d in items if d["kind"] in ("yt", "mi") and d.get("state") != "downloading"
                 and not d.get("video", {}).get("live")]
        if not items:
            return
        only_mi = all(d["kind"] == "mi" for d in items)
        modes = MI_MODES if only_mi else MODES
        m = QMenu(self)
        icons = {"video": "film", "wav": "music", "mp3": "music"}
        for mode, (label, tip) in modes.items():
            a = m.addAction(svg_icon(icons[mode], TEXT, 16), label)
            a.setToolTip(tip)
            a.triggered.connect(lambda _=False, md=mode: [self.start_download(d, md) for d in items
                                                          if not (d["kind"] == "mi" and md == "video")])
        m.setToolTipsVisible(True)
        m.exec(gpos)

    def _save_thumb(self, d: dict, path: str):
        pm = self.yt_thumbs.get(d["video"]["id"]) if d["kind"] == "yt" else instant_cover(d["item"]["color"])
        if pm and not pm.isNull():
            pm.save(str(THUMBS / (Path(path).name + ".jpg")), "JPG", 88)
            self.file_thumbs.pop(path, None)

    def start_download(self, d: dict, mode: str):
        if d.get("state") == "downloading":
            return
        if self.updating and d["kind"] == "yt":
            self.flash("Mise à jour de yt-dlp en cours… relance le téléchargement dans quelques secondes.")
            return
        d.update(state="downloading", pct=-1, status="Préparation…", error="")
        self.active += 1
        self.refresh_tiles()

        def progress(pct, text):
            d.update(pct=pct, status=text)
            self.refresh_tiles()

        def ok(path):
            self.active -= 1
            d["files"][mode] = path
            d["state"] = "done"
            self._save_thumb(d, path)
            self.refresh_tiles()
            self.refresh_library()
            self.flash(f"✔ « {tile_title(d)} » est prêt : glisse la vignette sur ta timeline.")

        def fail(msg):
            self.active -= 1
            d.update(state="error", error=msg)
            self.refresh_tiles()
            self.flash("✖ " + msg, 20000)
            if d["kind"] == "yt" and "robot" not in msg and "privée" not in msg:
                self.show_banner("Le téléchargement YouTube a échoué. YouTube a sans doute changé : une mise à jour "
                                 "de yt-dlp règle ça dans la plupart des cas (10 à 30 s).")

        if d["kind"] == "mi":
            self.run_task(myinstants_download, d["item"], mode, self.settings,
                          on_done=ok, on_fail=fail, on_progress=progress)
        else:
            self.run_task(download, d["video"], mode, self.settings,
                          on_done=ok, on_fail=fail, on_progress=progress)

    # ---------------------------------------------------------- fichiers
    def paths_of(self, d: dict) -> list[str]:
        if d["kind"] in ("yt", "mi"):
            return list(reversed(list(d.get("files", {}).values())))
        return [d["path"]]

    def thumb_for(self, d: dict) -> QPixmap | None:
        if d["kind"] == "yt":
            return self.yt_thumbs.get(d["video"]["id"])
        if d["kind"] == "mi":
            return instant_cover(d["item"]["color"])
        path = d["path"]
        if path in self.file_thumbs:
            return self.file_thumbs[path]
        cached = THUMBS / (Path(path).name + ".jpg")
        if cached.exists():
            pm = QPixmap(str(cached))
            self.file_thumbs[path] = pm
            return pm
        if is_video_file(path) and path not in self.thumb_jobs:
            self.thumb_jobs.add(path)
            self.run_task(video_frame_thumb, path, str(cached),
                          on_done=lambda _: self.lib_view.viewport().update())
        return None

    def _lib_files(self, fav_only=False) -> list[Path]:
        d = Path(self.settings.download_dir)
        try:
            files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXT]
        except OSError:
            return []
        if fav_only:
            files = [p for p in files if p.name in self.settings.favorites]
        return files

    def refresh_library(self, *_):
        all_files = self._lib_files()
        self.side_all.set_count(len(all_files))
        self.side_fav.set_count(sum(p.name in self.settings.favorites for p in all_files))
        if self.view not in ("all", "fav"):
            return
        files = self._lib_files(fav_only=self.view == "fav")
        kind = self.pill_group.checkedId()
        if kind == 1:
            files = [p for p in files if is_video_file(str(p))]
        elif kind == 2:
            files = [p for p in files if not is_video_file(str(p))]
        stats = {}
        for p in list(files):
            try:
                stats[p] = p.stat()
            except OSError:
                files.remove(p)
        mode = self.sort.currentIndex()
        if mode == 1:
            files.sort(key=lambda p: p.name.lower())
        elif mode == 2:
            files.sort(key=lambda p: -stats[p].st_size)
        else:
            files.sort(key=lambda p: -stats[p].st_mtime)
        durations = {Path(f).name: fmt_duration(st["video"].get("duration"))
                     for st in self.videos.values() for f in st.get("files", {}).values()}
        sel = {tile_data(it)["path"] for it in self.lib_view.selectedItems()}
        self.lib_view.clear()
        for p in files:
            it = QListWidgetItem()
            it.setData(ROLE, {"kind": "file", "path": str(p), "size": stats[p].st_size,
                              "dur": durations.get(p.name, "")})
            it.setSizeHint(QSize(CARD_W, CARD_H))
            it.setToolTip(str(p))
            self.lib_view.addItem(it)
            it.setSelected(str(p) in sel)
        self._update_header()

    def _double_click(self, it: QListWidgetItem):
        self.open_preview(tile_data(it))

    def _context_menu(self, view: TileView, pos: QPoint):
        it = view.itemAt(pos)
        if not it:
            return
        if not it.isSelected():
            view.clearSelection()
            it.setSelected(True)
        d = tile_data(it)
        m = QMenu(self)
        m.addAction(svg_icon("play", TEXT, 16), "Aperçu", lambda: self.open_preview(d))
        if d["kind"] in ("yt", "mi"):
            sel = [tile_data(i) for i in view.selectedItems()]
            sub = m.addMenu(svg_icon("download", TEXT, 16), "Télécharger")
            for mode, (label, _) in (MI_MODES if d["kind"] == "mi" else MODES).items():
                sub.addAction(label, lambda md=mode: [self.start_download(x, md) for x in sel])
            url = d["video"]["url"] if d["kind"] == "yt" else d["item"]["page_url"]
            m.addAction(svg_icon("external", TEXT, 16),
                        "Ouvrir sur YouTube" if d["kind"] == "yt" else "Ouvrir sur MyInstants",
                        lambda: QDesktopServices.openUrl(QUrl(url)))
            m.addAction("Copier le lien", lambda: QGuiApplication.clipboard().setText(url))
            if d.get("files"):
                m.addSeparator()
                m.addAction(svg_icon("folder", TEXT, 16), "Afficher dans l'Explorateur",
                            lambda: reveal_in_explorer(self.paths_of(d)[0]))
        else:
            fav = Path(d["path"]).name in self.settings.favorites
            m.addAction(svg_icon("star", TEXT, 16), "Retirer des favoris" if fav else "Ajouter aux favoris",
                        lambda: self.toggle_favorite(d["path"]))
            m.addAction(svg_icon("folder", TEXT, 16), "Afficher dans l'Explorateur",
                        lambda: reveal_in_explorer(d["path"]))
            m.addSeparator()
            m.addAction(svg_icon("trash", RED, 16), "Supprimer…", self._delete_selected)
        m.exec(view.viewport().mapToGlobal(pos))

    def _delete_selected(self):
        items = self.lib_view.selectedItems()
        if not items or QMessageBox.question(
                self, APP_NAME, f"Supprimer {len(items)} fichier(s) du disque ?") != QMessageBox.Yes:
            return
        if self.preview.d and self.preview.d.get("kind") == "file":
            self.preview.close_preview()
        for it in items:
            p = Path(tile_data(it)["path"])
            for f in (p, THUMBS / (p.name + ".jpg")):
                try:
                    f.unlink()
                except OSError:
                    pass
            for st in list(self.videos.values()) + list(self.instants.values()):
                st["files"] = {k: v for k, v in st.get("files", {}).items() if Path(v) != p}
        self.refresh_library()
        self.refresh_tiles()

    def open_folder(self):
        Path(self.settings.download_dir).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.settings.download_dir))

    def set_download_dir(self, d: str):
        self.settings.download_dir = d
        self.settings.save()
        self._watch_dir()
        self.refresh_library()
        self._update_action()

    def _watch_dir(self):
        if self.watcher.directories():
            self.watcher.removePaths(self.watcher.directories())
        Path(self.settings.download_dir).mkdir(parents=True, exist_ok=True)
        self.watcher.addPath(self.settings.download_dir)

    def set_on_top(self, on: bool, save: bool = True):
        self.settings.always_on_top = on
        if save:
            self.settings.save()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()

    # ------------------------------------------------- mise à jour yt-dlp
    def show_banner(self, text: str, button: bool = True):
        self.banner_lbl.setText(text)
        self.banner_btn.setVisible(button)
        self.banner.show()

    def run_ytdlp_update(self, silent: bool = False):
        if self.updating:
            return
        if self.active:
            msg = "Attends la fin des téléchargements en cours, puis relance la mise à jour."
            self.flash(msg)
            if self.settings_dialog:
                self.settings_dialog.upd_status.setText(msg)
            return
        self.updating = True
        channel = self.settings.ytdlp_channel
        self.show_banner(f"Mise à jour de yt-dlp ({'nightly' if channel == 'nightly' else 'stable'}) en cours…",
                         button=False)
        if self.settings_dialog:
            self.settings_dialog.set_updating(True, "Téléchargement et installation…")

        def done(res):
            self.updating = False
            self.settings.ytdlp_last_check = time.time()
            self.settings.save()
            if res["changed"]:
                text = (f"✔ yt-dlp mis à jour : {res['before']} → {res['after']}. "
                        "La fenêtre redémarre pour l'utiliser…")
                self.show_banner(text, button=False)
                if self.settings_dialog:
                    self.settings_dialog.set_updating(False, text)
                QTimer.singleShot(1500, self.restart_app)
                return
            elif channel == "stable":
                text = (f"yt-dlp est déjà à jour ({res['after']}). Si YouTube ne marche toujours pas, "
                        "passe le canal sur « Nightly » dans ⚙ Réglages puis remets à jour.")
            else:
                text = f"yt-dlp nightly est déjà à jour ({res['after']})."
            self.preview_cache.clear()
            self.show_banner(text, button=False)
            QTimer.singleShot(15000, lambda t=text: self.banner_lbl.text() == t and self.banner.hide())
            if self.settings_dialog:
                self.settings_dialog.set_updating(False, text)
                self.settings_dialog.refresh_versions()

        def fail(msg):
            self.updating = False
            text = "✖ " + msg + " (détails : ⚙ Réglages > Ouvrir le journal d'erreurs)"
            self.show_banner(text, button=True)
            if self.settings_dialog:
                self.settings_dialog.set_updating(False, text)

        self.run_task(update_ytdlp, channel, on_done=done, on_fail=fail)

    def restart_app(self):
        """Relance la fenêtre (même recherche) pour charger la nouvelle version de yt-dlp."""
        if self.active:                        # un téléchargement a démarré entre-temps : on attend
            QTimer.singleShot(3000, self.restart_app)
            return
        self.settings.save()
        args = [str(Path(__file__).resolve())]
        if self.view == "mi":
            args += ["--myinstants", self.mi_query]
        elif self.query:
            args += ["--youtube", self.query]
        server = getattr(self, "local_server", None)
        if server is not None:
            server.close()                     # la nouvelle fenêtre doit devenir la principale
        if QProcess.startDetached(sys.executable, args):
            os._exit(0)
        self.show_banner("yt-dlp est à jour. Ferme et rouvre la fenêtre pour l'utiliser.", button=False)

    def _auto_check_ytdlp(self):
        """Au démarrage (au plus toutes les 6 h) : regarde si une nouvelle version de yt-dlp existe."""
        if time.time() - self.settings.ytdlp_last_check < 6 * 3600:
            return
        channel = self.settings.ytdlp_channel

        def done(version):
            self.settings.ytdlp_last_check = time.time()
            self.settings.save()
            if not version:
                return
            if self.settings.ytdlp_auto_update and not self.active:
                self.run_ytdlp_update(silent=True)
            else:
                self.show_banner(f"Une nouvelle version de yt-dlp est disponible ({version}). Elle corrige souvent "
                                 "les problèmes de téléchargement YouTube.")
        self.run_task(ytdlp_update_available, channel, on_done=done)

    # ---------------------------------------- messages d'une 2e instance
    def handle_message(self, msg: dict):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        q = (msg.get("query") or "").strip()
        src = msg.get("source") or "yt"
        if src == "mi":
            self.show_view("mi")
            if q:
                self.search.setText(q)
                self.mi_search(q)
        elif q:
            self.search.setText(q)
            self.new_search(q, "yt")

    def closeEvent(self, e):
        if self.active and QMessageBox.question(
                self, APP_NAME, "Des téléchargements sont en cours. Quitter quand même ?") != QMessageBox.Yes:
            e.ignore()
            return
        self.settings.save()
        e.accept()
        os._exit(0)


# --------------------------------------------------------------------------- #
#  Lancement (une seule fenêtre : un 2e lancement réveille la première)        #
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> dict:
    msg = {"source": "yt", "query": ""}
    it = iter(argv)
    for a in it:
        if a in ("--youtube", "--myinstants"):
            msg["source"] = "mi" if a == "--myinstants" else "yt"
            msg["query"] = next(it, "")
    return msg


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YouTubePourResolve")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    msg = parse_args(sys.argv[1:])
    server_name = "YouTubePourResolve-" + "".join(c for c in getpass.getuser() if c.isalnum())

    sock = QLocalSocket()
    sock.connectToServer(server_name)
    if sock.waitForConnected(400):          # déjà ouverte : on lui passe la demande et on s'arrête
        sock.write(json.dumps(msg).encode("utf-8"))
        sock.waitForBytesWritten(1000)
        sock.disconnectFromServer()
        return

    app.setFont(QFont("Segoe UI" if IS_WIN else "Sans Serif", 10))
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()

    QLocalServer.removeServer(server_name)
    server = QLocalServer(win)
    server.listen(server_name)
    win.local_server = server

    def incoming():
        conn = server.nextPendingConnection()

        def read():
            try:
                win.handle_message(json.loads(bytes(conn.readAll()).decode("utf-8") or "{}"))
            except Exception:
                win.handle_message({})
        conn.readyRead.connect(read)
    server.newConnection.connect(incoming)

    if msg["query"] or msg["source"] == "mi":
        QTimer.singleShot(0, lambda: win.handle_message(msg))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
