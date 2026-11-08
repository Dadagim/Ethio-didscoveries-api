"""Validation and helpers for reusable media records.

Only provider-aware, server-built playback data is stored. Client-supplied
iframe HTML is never accepted.
"""

import re
from urllib.parse import parse_qs, urlparse

from .models import MediaAsset, MediaAttachment


class UnsupportedVideoURLError(ValueError):
    """Raised when a URL is not a supported external video."""


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

WATCH_PATHS = {"/watch"}
PATH_PREFIXES = ("/embed/", "/shorts/", "/live/")


def _extract_video_id(host, path, query):
    segments = [segment for segment in path.split("/") if segment]

    if host in {"youtu.be", "www.youtu.be"}:
        return segments[0] if len(segments) == 1 else None

    if path in WATCH_PATHS or path.rstrip("/") in WATCH_PATHS:
        values = parse_qs(query).get("v", [])
        return values[0] if len(values) == 1 else None

    if path.startswith(PATH_PREFIXES) and len(segments) == 2:
        return segments[1]

    return None


def parse_youtube_url(raw_url):
    """Return safe, canonical YouTube metadata or raise a clear error."""

    if not isinstance(raw_url, str):
        raise UnsupportedVideoURLError("Enter a YouTube video URL.")

    value = raw_url.strip()
    if not value:
        raise UnsupportedVideoURLError("Enter a YouTube video URL.")
    if len(value) > 500:
        raise UnsupportedVideoURLError("That URL is too long.")
    if "<" in value or ">" in value:
        raise UnsupportedVideoURLError("Paste a video URL, not embed HTML.")

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise UnsupportedVideoURLError("Only http and https video links are supported.")
    if parsed.username or parsed.password:
        raise UnsupportedVideoURLError("That URL is not allowed.")

    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        raise UnsupportedVideoURLError(
            "Only YouTube links are supported right now."
        )

    video_id = _extract_video_id(host, parsed.path, parsed.query)
    if not video_id or not VIDEO_ID_RE.match(video_id):
        raise UnsupportedVideoURLError("That YouTube link does not contain a valid video ID.")

    return {
        "provider": MediaAsset.Provider.YOUTUBE,
        "external_id": video_id,
        "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
        "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def get_or_create_external_video(owner, raw_url, title=""):
    """Reuse one asset per provider video and refresh its safe URLs."""

    info = parse_youtube_url(raw_url)
    asset, created = MediaAsset.objects.get_or_create(
        provider=info["provider"],
        external_id=info["external_id"],
        defaults={
            "owner": owner,
            "kind": MediaAsset.Kind.EXTERNAL_VIDEO,
            "source": MediaAsset.Source.EXTERNAL,
            "canonical_url": info["canonical_url"],
            "embed_url": info["embed_url"],
            "thumbnail_url": info["thumbnail_url"],
            "title": title.strip()[:200],
            "status": MediaAsset.Status.READY,
        },
    )

    if created:
        return asset

    changed = []
    for field in ("canonical_url", "embed_url", "thumbnail_url"):
        if getattr(asset, field) != info[field]:
            setattr(asset, field, info[field])
            changed.append(field)
    if title and asset.title != title.strip()[:200]:
        asset.title = title.strip()[:200]
        changed.append("title")
    if changed:
        changed.append("updated_at")
        asset.save(update_fields=changed)
    return asset


def attach_external_video(target, raw_url, *, role=MediaAttachment.Role.EXPLANATION, title=""):
    """Attach a validated external video to any object with a generic relation."""

    asset = get_or_create_external_video(target.author, raw_url, title=title)
    attachment, _ = target.media_attachments.get_or_create(
        asset=asset,
        defaults={"role": role, "position": 0},
    )
    return attachment


def remove_external_videos(target):
    """Detach external videos from a target without deleting the shared asset."""

    return target.media_attachments.filter(
        asset__kind=MediaAsset.Kind.EXTERNAL_VIDEO,
        asset__source=MediaAsset.Source.EXTERNAL,
    ).delete()
