from fastapi import FastAPI, HTTPException, Response, Cookie, status
from firebase_admin import auth, exceptions, credentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

import firebase_admin
import datetime
import dotenv
import time
import json
import os

dotenv.load_dotenv()
service_account_str = os.getenv("SERVICE_CREDENTIALS")

if not service_account_str:
    raise ValueError("SERVICE_CREDENTIALS environment variable is not set")

# 2. Parse the JSON string into a dictionary
service_account_info = json.loads(service_account_str)
cred = credentials.Certificate(service_account_info)
os.environ["GOOGLE_CLOUD_PROJECT"] = "turinflow-app"

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://turinflow.com.br",
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id_token: str = Field(..., alias="idToken")

@app.post("/sessionLogin")
def session_login(payload: LoginRequest, response: Response):
    id_token = payload.id_token

    try:
        decoded_claims = auth.verify_id_token(id_token, check_revoked=True)
        # Only process if the user signed in within the last 5 minutes.
        if time.time() - decoded_claims.get("auth_time", "300") > 2 * 60:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail = "Sign-In is required")

        expired_in = datetime.timedelta(days=7)
        session_cookie = auth.create_session_cookie(id_token, expires_in=expired_in)

        response.set_cookie(key="turin_session", domain=".turinflow.com.br", value=session_cookie, max_age=int(expired_in.total_seconds()), httponly=True, secure=True, samesite="lax")
        return {"status": "200 OK"}

    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token")

    except exceptions.FirebaseError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to create session cookie")

@app.post("/sessionLogout")
def session_logout(response: Response, turin_session: str | None = Cookie(default=None)):
    response.delete_cookie(key="turin_session", domain=".turinflow.com.br", httponly=True, secure=True, samesite="lax")

    if turin_session:
        try:
            decoded_claims = auth.verify_session_cookie(turin_session)
            auth.revoke_refresh_tokens(decoded_claims.get("sub", "None"))

        except (auth.InvalidSessionCookieError, exceptions.FirebaseError):
            pass

        return {"status": "200 OK", "message": "Logged out"}
