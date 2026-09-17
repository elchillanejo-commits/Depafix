from fastapi import Request, HTTPException
async def verify_auth(request: Request):
    key = request.headers.get("X-API-Key")
    auth = request.headers.get("Authorization")
    if not (key or auth): raise HTTPException(status_code=401)
    return {"user": "verified"}
