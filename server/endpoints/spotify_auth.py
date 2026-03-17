"""Spotify OAuth callback and auth status endpoints for BITOS."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["spotify"])


@router.get("/spotify/auth")
async def spotify_auth_start():
    """Redirect to Spotify OAuth authorization page."""
    from integrations.spotify_adapter import get_spotify

    sp = get_spotify()
    if not sp.installed:
        return HTMLResponse(
            "<h2>Spotify integration unavailable</h2>"
            "<p>spotipy is not installed. Run: <code>pip install spotipy</code></p>",
            status_code=503,
        )

    auth_url = sp.get_auth_url()
    if not auth_url:
        return HTMLResponse(
            "<h2>Spotify not configured</h2>"
            "<p>Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env</p>",
            status_code=503,
        )

    return RedirectResponse(auth_url)


@router.get("/callback/spotify")
async def spotify_auth_callback(request: Request):
    """Handle Spotify OAuth redirect with authorization code."""
    from integrations.spotify_adapter import get_spotify

    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        logger.warning("spotify_auth_denied: %s", error)
        return HTMLResponse(
            f"<h2>Spotify authorization denied</h2><p>{error}</p>", status_code=400
        )

    if not code:
        return HTMLResponse(
            "<h2>Missing authorization code</h2>", status_code=400
        )

    sp = get_spotify()
    ok = sp.handle_auth_callback(code)
    if ok:
        return HTMLResponse(
            "<h2>Spotify connected!</h2>"
            "<p>You can close this page. BITOS now has access to your Spotify account.</p>"
        )
    else:
        return HTMLResponse(
            "<h2>Authentication failed</h2>"
            "<p>Could not exchange authorization code. Check server logs.</p>",
            status_code=500,
        )


@router.get("/spotify/status")
async def spotify_status():
    """Check Spotify connection status."""
    from integrations.spotify_adapter import get_spotify

    sp = get_spotify()
    return JSONResponse({
        "installed": sp.installed,
        "connected": sp.available,
    })


@router.get("/spotify/now-playing")
async def spotify_now_playing():
    """Get currently playing track."""
    from integrations.spotify_adapter import get_spotify

    sp = get_spotify()
    if not sp.available:
        return JSONResponse({"error": "Spotify not connected"}, status_code=503)

    now = sp.get_now_playing()
    if not now:
        return JSONResponse({"playing": False})

    return JSONResponse(now)
