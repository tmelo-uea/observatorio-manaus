import os
import re
import subprocess
import feedparser
import requests
from datetime import datetime

from db.connection import get_session
from db.models import Article, Source


def _resolve_rss_url(channel_url: str) -> str | None:
    """Converte uma URL de canal do YouTube para a URL do RSS feed."""
    if "feeds/videos.xml" in channel_url:
        return channel_url
    try:
        resp = requests.get(
            channel_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]{22})"', resp.text)
        if not match:
            return None
        channel_id = match.group(1)
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    except Exception:
        return None


def _captions(video_id: str) -> str | None:
    """Busca legendas automáticas do YouTube (sem download)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        segments = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["pt", "pt-BR", "en"]
        )
        return " ".join(s["text"] for s in segments)
    except Exception as e:
        print(f"  [captions] {video_id}: {e}")
        return None


def _get_cookies_file() -> str | None:
    """Decodifica cookies do YouTube da variável de ambiente para arquivo temporário."""
    import base64, gzip, tempfile
    b64 = os.getenv("YOUTUBE_COOKIES_B64")
    if not b64:
        return None
    try:
        data = gzip.decompress(base64.b64decode(b64))
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"  [cookies] Erro ao decodificar: {e}")
        return None


def _groq_transcribe(video_url: str, video_id: str) -> str | None:
    """Baixa o áudio e transcreve via Groq Whisper."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    audio_path = f"/tmp/{video_id}.mp3"
    cookies_file = _get_cookies_file()
    cmd = [
        "yt-dlp", "-x",
        "--audio-format", "mp3",
        "--audio-quality", "9",
        "-o", audio_path,
        "--no-playlist",
        "--quiet",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
    ]
    if cookies_file:
        cmd += ["--cookies", cookies_file]
    cmd.append(video_url)

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=180)
        if cookies_file and os.path.exists(cookies_file):
            os.remove(cookies_file)

        if proc.returncode != 0 or not os.path.exists(audio_path):
            stderr = proc.stderr.decode(errors="replace").strip()
            print(f"  [yt-dlp] {video_id} falhou (code {proc.returncode}): {stderr[:200]}")
            return None

        if os.path.getsize(audio_path) > 24 * 1024 * 1024:  # limite 25 MB do Groq
            return None

        from groq import Groq
        client = Groq(api_key=api_key)
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                file=(f"{video_id}.mp3", f),
                model="whisper-large-v3",
                language="pt",
            )
        print(f"  [Groq] {video_id}: transcrição OK ({len(result.text)} chars)")
        return result.text
    except Exception as e:
        print(f"  [Groq] {video_id} erro: {e}")
        return None
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def _get_transcript(video_id: str, video_url: str) -> str | None:
    """Tenta legendas do YouTube; cai no Groq se não houver."""
    transcript = _captions(video_id)
    if transcript:
        return transcript
    return _groq_transcribe(video_url, video_id)


def _video_id_from_url(url: str) -> str | None:
    match = re.search(r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None


def _collect_channel(source: Source, session) -> int:
    rss_url = _resolve_rss_url(source.rss_url)
    if not rss_url:
        print(f"  [{source.name}] Não foi possível resolver o RSS.")
        return 0

    if rss_url != source.rss_url:
        source.rss_url = rss_url
        session.flush()

    feed = feedparser.parse(rss_url)
    collected = 0

    for entry in feed.entries:
        url = entry.get("link", "")
        if not url or session.query(Article).filter_by(url=url).first():
            continue

        video_id = _video_id_from_url(url)
        transcript = _get_transcript(video_id, url) if video_id else None

        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6])

        summary = re.sub(r"<[^>]+>", "", entry.get("summary", "") or "").strip()

        article = Article(
            title=(entry.get("title", "") or "")[:500],
            url=url[:767],
            summary=summary or None,
            published_at=published,
            source_id=source.id,
            transcript=transcript,
        )
        session.add(article)
        collected += 1

    session.commit()
    return collected


def run_youtube_collection() -> int:
    session = get_session()
    total = 0
    try:
        sources = session.query(Source).filter_by(type="youtube", active=True).all()
        for source in sources:
            n = _collect_channel(source, session)
            if n:
                print(f"  {source.name}: {n} novos vídeos")
            total += n
    finally:
        session.close()
    return total
