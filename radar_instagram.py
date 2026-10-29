#!/usr/bin/env python3
"""
radar_instagram.py — Bio + últimos posts usando instagrapi (API móvil).
Uso: python3 radar_instagram.py
Requiere: pip install instagrapi
Sesión: ~/.config/instagrapi_session.json (se crea en el primer login)
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import (
    ClientThrottledError,
    LoginRequired,
    ChallengeRequired,
    TwoFactorRequired,
)

PERFILES = ["transistorgigs", "salametronomo", "epicentrosantiago"]
MAX_POSTS = 6
SALIDA = Path("logs/instagram_pymes.json")
SESSION_FILE = Path.home() / ".config" / "instagrapi_session.json"
DELAY_ENTRE_PERFILES = 8  # segundos

# ⚠️ USA UNA CUENTA SECUNDARIA, NUNCA TU CUENTA PERSONAL
IG_USER = "TU_USUARIO_SECUNDARIO"
IG_PASS = "TU_CONTRASEÑA"


def get_client() -> Client:
    """Login o reutiliza sesión guardada."""
    cl = Client()
    cl.delay_range = [2, 5]  # jitter entre requests

    if SESSION_FILE.exists():
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USER, IG_PASS)  # revalida sin forzar nuevo device
            cl.get_timeline_feed()  # probe: confirma que la sesión vive
            print(f"[INFO] Sesión reutilizada: {SESSION_FILE}")
            return cl
        except Exception as e:
            print(f"[WARN] Sesión guardada inválida ({type(e).__name__}). Relogin…")

    print("[INFO] Login nuevo…")
    cl.login(IG_USER, IG_PASS)
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(SESSION_FILE)
    print(f"[INFO] Sesión guardada: {SESSION_FILE}")
    return cl


def scrape_perfil(username: str, cl: Client) -> dict:
    base = {"username": username, "scraped_at": datetime.now(timezone.utc).isoformat()}
    try:
        user_id = cl.user_id_from_username(username)
        info = cl.user_info(user_id)
        base.update({
            "full_name": info.full_name,
            "biography": info.biography,
            "followers": info.follower_count,
            "followees": info.following_count,
            "posts_count": info.media_count,
            "is_private": info.is_private,
            "external_url": info.external_url,
            "profile_pic": str(info.profile_pic_url),
        })
        if info.is_private:
            base["error"] = "perfil_privado"
            return base

        posts = []
        for m in cl.user_medias(user_id, amount=MAX_POSTS):
            posts.append({
                "shortcode": m.code,
                "date_utc": m.taken_at.isoformat(),
                "caption": (m.caption_text or "")[:500],
                "likes": m.like_count,
                "comments": m.comment_count,
                "is_video": m.media_type == 2,
                "url": f"https://www.instagram.com/p/{m.code}/",
            })
        base["recent_posts"] = posts
    except ClientThrottledError:
        base["error"] = "rate_limit_429"
        raise
    except Exception as e:
        base["error"] = f"{type(e).__name__}: {e}"
    return base


def main() -> None:
    try:
        cl = get_client()
    except (ChallengeRequired, TwoFactorRequired) as e:
        print(f"[ERROR] Instagram pide verificación ({type(e).__name__}).")
        print("        Abre la app con la cuenta secundaria, aprueba el login y vuelve a correr.")
        return
    except LoginRequired as e:
        print(f"[ERROR] Login rechazado: {e}")
        return
    except Exception as e:
        print(f"[ERROR] Fallo de login: {type(e).__name__}: {e}")
        return

    resultados = []
    for username in PERFILES:
        try:
            r = scrape_perfil(username, cl)
            resultados.append(r)
        except ClientThrottledError:
            resultados.append({
                "username": username,
                "error": "rate_limit_429",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
            print(f"[WARN] 429 en @{username}. Abortando lote.")
            break
        time.sleep(DELAY_ENTRE_PERFILES)

    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(resultados),
        "ok": sum(1 for r in resultados if "error" not in r),
        "profiles": resultados,
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {SALIDA.resolve()} | ok={payload['ok']}/{payload['count']}")
    for r in resultados:
        estado = "ERR " + r["error"] if "error" in r else f"OK  {len(r.get('recent_posts', []))} posts"
        print(f"   @{r['username']:<28} {estado}")


if __name__ == "__main__":
    main()
