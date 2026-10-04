"""
music_tagger.py
---------------
Enriquece arquivos MP3 com metadados completos (ID3 tags) após o download:
  - Limpeza do título bruto do YouTube
  - Busca no MusicBrainz por artista, álbum, ano, gênero e número de faixa
  - Capa: imagem oficial do MusicBrainz (Cover Art Archive) ou thumbnail do YouTube
  - Escrita das tags via mutagen (ID3v2.4)

Não requer nenhuma API key — usa apenas MusicBrainz (CC0) e URLs públicas.
"""

import re
import time
import logging
from pathlib import Path
from typing import Optional

import httpx
from mutagen.id3 import (
    ID3, ID3NoHeaderError,
    TIT2, TPE1, TALB, TDRC, TRCK, TCON, APIC,
    TPE2, COMM,
)

try:
    import musicbrainzngs as mb
    mb.set_useragent("AssistenteBot", "1.0", "https://github.com/Paulos19/agent")
    _MB_AVAILABLE = True
except ImportError:
    _MB_AVAILABLE = False

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 1. Limpeza do título bruto do YouTube
# ──────────────────────────────────────────────

_CLEANUP_PATTERNS = [
    r'\(?\bofficial\s*(music\s*)?video\b\)?',
    r'\(?\bofficial\s*audio\b\)?',
    r'\(?\bofficial\s*lyric[s]?\s*video\b\)?',
    r'\(?\blyric[s]?\s*video\b\)?',
    r'\(?\blyric[s]?\b\)?',
    r'\(?\baudio\s*oficial\b\)?',
    r'\(?\bvideo\s*oficial\b\)?',
    r'\(?\bvídeo\s*oficial\b\)?',
    r'\(?\bclipe\s*oficial\b\)?',
    r'\(?\bofficial\s*clip\b\)?',
    r'\(?\b(hd|hq|4k|8k|1080p|720p)\b\)?',
    r'\[?\b(official\s*)?(music\s*)?video\b\]?',
    r'\[?\b(hd|hq|4k|8k|1080p|720p)\b\]?',
    r'\[?\blyric[s]?\b\]?',
    r'\[?\baudio\b\]?',
    r'#\w+',
    r'【[^】]*】',
    r'「[^」]*」',
]


def _clean_title(raw: str) -> str:
    """Remove lixo de títulos do YouTube, preservando nome da música e feat."""
    t = raw
    for pat in _CLEANUP_PATTERNS:
        t = re.sub(pat, '', t, flags=re.IGNORECASE)
    t = re.sub(r'[\(\[]\s*[\)\]]', '', t)
    t = re.sub(r'\s{2,}', ' ', t)
    t = re.sub(r'\s*[-–—]\s*$', '', t)
    return t.strip()


def _parse_artist_title(raw_title: str, raw_uploader: str) -> tuple:
    """
    Extrai artista e título a partir do título do YouTube.
    Padrões: 'Artista - Música', 'Artista: Música', 'Música by Artista'.
    Fallback: uploader como artista, título limpo como música.
    """
    clean = _clean_title(raw_title)

    # Padrão: Artista - Título
    sep_match = re.match(r'^(.+?)\s*[-–—:]\s*(.+)$', clean)
    if sep_match:
        artist_part = sep_match.group(1).strip()
        title_part = sep_match.group(2).strip()
        if len(artist_part) < len(title_part) + 30:
            return artist_part, title_part

    # Padrão: "Título by Artista"
    by_match = re.match(r'^(.+?)\s+by\s+(.+)$', clean, re.IGNORECASE)
    if by_match:
        return by_match.group(2).strip(), by_match.group(1).strip()

    # Fallback: uploader como artista
    uploader = re.sub(
        r'\s*([-–—]\s*(official|topic|vevo|music|lyrics?)\s*)',
        '', raw_uploader, flags=re.IGNORECASE
    ).strip()
    return uploader, clean


# ──────────────────────────────────────────────
# 2. Busca no MusicBrainz
# ──────────────────────────────────────────────

def _mb_search(artist: str, title: str) -> Optional[dict]:
    """Consulta MusicBrainz por recording + release."""
    if not _MB_AVAILABLE:
        return None
    try:
        result = mb.search_recordings(recording=title, artist=artist, limit=5)
        recordings = result.get("recording-list", [])
        if not recordings:
            return None

        rec = recordings[0]
        mb_title = rec.get("title", title)
        mb_artist = rec.get("artist-credit-phrase", artist)

        release_list = rec.get("release-list", [])
        if not release_list:
            return {"title": mb_title, "artist": mb_artist}

        release = release_list[0]
        album = release.get("title", "")
        year = ""
        date_str = release.get("date", "")
        if date_str:
            year = date_str[:4]

        track_number = ""
        medium_list = release.get("medium-list", [])
        if medium_list:
            track_list = medium_list[0].get("track-list", [])
            if track_list:
                track_number = track_list[0].get("number", "")

        release_id = release.get("id", "")

        return {
            "title": mb_title,
            "artist": mb_artist,
            "album": album,
            "year": year,
            "track_number": track_number,
            "cover_release_id": release_id,
        }
    except Exception as e:
        logger.debug(f"[MusicBrainz] Falha na busca: {e}")
        return None


def _mb_get_cover(release_id: str) -> Optional[bytes]:
    """Baixa a capa do álbum via Cover Art Archive (MusicBrainz)."""
    if not release_id:
        return None
    try:
        cover_data = mb.get_image_front(release_id, size="500")
        if cover_data:
            return cover_data
    except Exception:
        pass
    try:
        url = f"https://coverartarchive.org/release/{release_id}/front-500"
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# 3. Download da thumbnail do YouTube
# ──────────────────────────────────────────────

def _download_thumbnail(url: str) -> Optional[bytes]:
    """Baixa a thumbnail do YouTube como bytes JPEG."""
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception as e:
        logger.debug(f"[Thumbnail] Falha ao baixar: {e}")
    return None


def _best_thumbnail_url(info: dict) -> Optional[str]:
    """Extrai a URL da melhor thumbnail disponível nas infos do yt-dlp."""
    thumbnails = info.get("thumbnails") or []
    sorted_thumbs = sorted(
        [t for t in thumbnails if t.get("url")],
        key=lambda t: t.get("width", 0),
        reverse=True,
    )
    if sorted_thumbs:
        return sorted_thumbs[0]["url"]
    return info.get("thumbnail")


# ──────────────────────────────────────────────
# 4. Escrita das tags ID3 no MP3
# ──────────────────────────────────────────────

def _write_mp3_tags(
    file_path: Path,
    title: str,
    artist: str,
    album: str = "",
    year: str = "",
    track_number: str = "",
    genre: str = "",
    cover_bytes: Optional[bytes] = None,
    album_artist: str = "",
    comment: str = "",
) -> None:
    """Escreve tags ID3v2.4 no arquivo MP3 usando mutagen."""
    try:
        tags = ID3(str(file_path))
    except ID3NoHeaderError:
        tags = ID3()

    tags.clear()
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=artist))

    if album:
        tags.add(TALB(encoding=3, text=album))
    if year:
        tags.add(TDRC(encoding=3, text=year))
    if track_number:
        tags.add(TRCK(encoding=3, text=str(track_number)))
    if genre:
        tags.add(TCON(encoding=3, text=genre))
    if album_artist:
        tags.add(TPE2(encoding=3, text=album_artist))
    if comment:
        tags.add(COMM(encoding=3, lang="por", desc="", text=comment))

    if cover_bytes:
        mime = "image/jpeg"
        if cover_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            mime = "image/png"
        tags.add(APIC(
            encoding=3,
            mime=mime,
            type=3,
            desc="Cover",
            data=cover_bytes,
        ))

    tags.save(str(file_path), v2_version=4)
    logger.info(f"[Tagger] Tags escritas em '{file_path.name}'")


# ──────────────────────────────────────────────
# 5. Função principal pública
# ──────────────────────────────────────────────

def enrich_mp3_metadata(file_path: Path, yt_info: dict) -> dict:
    """
    Pipeline completo de enriquecimento de metadados para um MP3 baixado.

    Parâmetros:
        file_path: Caminho do arquivo .mp3 já baixado.
        yt_info:   Dict de info do yt-dlp (com 'title', 'uploader', 'thumbnails', etc.)

    Retorna dict com os metadados finais aplicados.
    """
    raw_title = yt_info.get("title", "")
    raw_uploader = yt_info.get("uploader", "")

    # 1. Parse artista + título
    artist, title = _parse_artist_title(raw_title, raw_uploader)
    logger.info(f"[Tagger] Artista='{artist}' | Título='{title}'")

    # 2. MusicBrainz lookup
    mb_data = None
    if _MB_AVAILABLE:
        time.sleep(0.5)  # respeita rate limit da MusicBrainz (1 req/s)
        mb_data = _mb_search(artist, title)
        if mb_data:
            logger.info(f"[Tagger] MusicBrainz encontrou: {mb_data}")

    # 3. Mescla dados: MusicBrainz tem prioridade, YouTube é fallback
    final_title = (mb_data or {}).get("title") or title
    final_artist = (mb_data or {}).get("artist") or artist
    final_album = (mb_data or {}).get("album", "")
    final_year = (mb_data or {}).get("year", "") or str(yt_info.get("upload_date", ""))[:4]
    final_track = (mb_data or {}).get("track_number", "")
    final_genre = (mb_data or {}).get("genre", "")

    # 4. Capa: Cover Art Archive → thumbnail do YouTube
    cover_bytes = None
    release_id = (mb_data or {}).get("cover_release_id", "")
    if release_id:
        cover_bytes = _mb_get_cover(release_id)
        if cover_bytes:
            logger.info("[Tagger] Capa obtida do Cover Art Archive (MusicBrainz)")

    if not cover_bytes:
        thumb_url = _best_thumbnail_url(yt_info)
        cover_bytes = _download_thumbnail(thumb_url)
        if cover_bytes:
            logger.info("[Tagger] Capa obtida da thumbnail do YouTube")

    # 5. Escreve tags no arquivo
    _write_mp3_tags(
        file_path=file_path,
        title=final_title,
        artist=final_artist,
        album=final_album,
        year=final_year,
        track_number=final_track,
        genre=final_genre,
        cover_bytes=cover_bytes,
        album_artist=final_artist,
        comment=f"Baixado via AssistenteBot | {yt_info.get('webpage_url', '')}",
    )

    return {
        "title": final_title,
        "artist": final_artist,
        "album": final_album,
        "year": final_year,
        "track_number": final_track,
        "genre": final_genre,
        "cover_source": "musicbrainz" if (release_id and cover_bytes) else ("youtube" if cover_bytes else "none"),
    }
