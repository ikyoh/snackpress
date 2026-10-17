"""Personal accounts, opaque cookie sessions and one-use e-mail links."""

import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import AccountToken, LoginSession, User

router = APIRouter(prefix="/api/auth", tags=["accounts"])
COOKIE = "snackpress_session"
SESSION_AGE = 7 * 24 * 3600
_hash_slots = threading.BoundedSemaphore(2)
_rate_lock = threading.Lock()
_rates: dict[str, list[float]] = {}


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def engine():
    from .main import engine

    return engine


def public_url():
    value = os.environ.get("SNACKPRESS_PUBLIC_URL", "http://127.0.0.1:5173").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path:
        raise HTTPException(503, "L’adresse publique de Snackpress est mal configurée.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(503, "HTTPS est requis pour les comptes utilisateurs.")
    return value


def protect(request: Request):
    # Browsers cannot add this header to a cross-origin form. No CORS is enabled.
    if request.headers.get("X-Snackpress-Request") != "1":
        raise HTTPException(403, "Requête refusée. Rechargez la page.")
    origin = request.headers.get("origin")
    if origin and origin != public_url():
        raise HTTPException(403, "Origine de la requête refusée.")


def rate_limit(request: Request, email: str = ""):
    stamp = time.monotonic()
    peer = request.client.host if request.client else "unknown"
    # Do not trust arbitrary X-Forwarded-For headers from clients.
    keys = [(f"ip:{peer}", 40)]
    if email:
        keys.append((f"email:{digest(email)}", 12))
    with _rate_lock:
        for key in list(_rates):
            _rates[key] = [t for t in _rates[key] if t > stamp - 900]
            if not _rates[key]:
                del _rates[key]
        if len(_rates) > 10000:
            raise HTTPException(429, "Trop de demandes. Réessayez dans quinze minutes.")
        if any(len(_rates.get(key, [])) >= limit for key, limit in keys):
            raise HTTPException(429, "Trop de demandes. Réessayez dans quinze minutes.")
        for key, _ in keys:
            _rates.setdefault(key, []).append(stamp)


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str, salt: bytes | None = None):
    salt = salt or secrets.token_bytes(16)
    with _hash_slots:
        hashed = hashlib.scrypt(
            password.encode(), salt=salt, n=2**17, r=8, p=1, maxmem=256 * 1024 * 1024
        )
    return f"scrypt${salt.hex()}${hashed.hex()}"


def check_password(password: str, encoded: str | None):
    if not encoded:
        # Same expensive operation for an unknown / unverified account.
        hash_password(password)
        return False
    _, salt, _ = encoded.split("$")
    return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)), encoded)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailInput(Input):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@<>]+@[^\s@<>.]+(?:\.[^\s@<>.]+)+", value):
            raise ValueError("Saisissez une adresse e-mail valide.")
        return value


class Credentials(EmailInput):
    password: str = Field(max_length=128)


class TokenPassword(Input):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=15, max_length=128)


class AccountResponse(BaseModel):
    id: str
    email: str


class Message(BaseModel):
    message: str


def send_mail(email: str, kind: str, token: str):
    base = public_url()
    link = f"{base}/#" + urlencode({"account": kind, "token": token})
    mail = EmailMessage()
    mail["From"] = os.environ.get("SNACKPRESS_MAIL_FROM", "")
    mail["To"] = email
    mail["Subject"] = (
        "Votre compte Snackpress" if kind == "verify" else "Votre mot de passe Snackpress"
    )
    action = (
        "choisir votre mot de passe et activer votre compte"
        if kind == "verify"
        else ("choisir un nouveau mot de passe")
    )
    mail.set_content(
        f"Bonjour,\n\nPour {action}, ouvrez ce lien :\n{link}\n\n"
        "Ce lien est personnel, utilisable une seule fois et valable 30 minutes.\n"
        "Si vous n’avez pas fait cette demande, ignorez ce message.\n\nSnackpress"
    )
    if os.environ.get("SNACKPRESS_MAIL_MODE") == "file":
        if urlsplit(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise HTTPException(503, "Le mode e-mail local est réservé au développement.")
        from .main import DATA

        folder = DATA / "mail-outbox"
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / f"{uuid4().hex}.eml"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(mail.as_string())
        return
    host = os.environ.get("SNACKPRESS_SMTP_HOST")
    if not host or not mail["From"]:
        raise HTTPException(503, "L’envoi des e-mails doit être configuré par l’administrateur.")
    try:
        mode = os.environ.get("SNACKPRESS_SMTP_SECURITY", "starttls")
        if mode not in {"starttls", "ssl"}:
            raise ValueError("SMTP requires TLS")
        port = int(os.environ.get("SNACKPRESS_SMTP_PORT", "465" if mode == "ssl" else "587"))
        smtp_type = smtplib.SMTP_SSL if mode == "ssl" else smtplib.SMTP
        kwargs = {"context": ssl.create_default_context()} if mode == "ssl" else {}
        with smtp_type(host, port, timeout=10, **kwargs) as smtp:
            if mode == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            username = os.environ.get("SNACKPRESS_SMTP_USERNAME")
            if username:
                smtp.login(username, os.environ.get("SNACKPRESS_SMTP_PASSWORD", ""))
            smtp.send_message(mail)
    except (OSError, ValueError, smtplib.SMTPException):
        raise HTTPException(503, "E-mail non envoyé. Réessayez plus tard.") from None


def issue_link(db: Session, user: User, kind: str):
    token = secrets.token_urlsafe(32)
    # Invalidate previous links of this kind only after successful delivery.
    send_mail(user.email, kind, token)
    db.execute(
        delete(AccountToken).where(AccountToken.user_id == user.id, AccountToken.kind == kind)
    )
    db.add(
        AccountToken(
            token_hash=digest(token),
            user_id=user.id,
            kind=kind,
            expires_at=now() + timedelta(minutes=30),
        )
    )


def current_user(request: Request):
    token = request.cookies.get(COOKIE, "")
    with Session(engine()) as db:
        session = db.get(LoginSession, digest(token)) if token else None
        if not session or session.expires_at <= now():
            raise HTTPException(401, "Connectez-vous pour retrouver vos configurations.")
        user = db.get(User, session.user_id)
        if not user or not user.verified:
            raise HTTPException(401, "Connectez-vous pour retrouver vos configurations.")
        expected = request.headers.get("X-Snackpress-Account")
        if expected and expected != user.id:
            raise HTTPException(
                409, "Le compte actif a changé. Rechargez la page avant de réessayer."
            )
        return AccountResponse(id=user.id, email=user.email)


@router.get("/me", response_model=AccountResponse)
def me(user: AccountResponse = Depends(current_user)):
    return user


@router.post("/register", response_model=Message, dependencies=[Depends(protect)])
def register(data: EmailInput, request: Request):
    rate_limit(request, data.email)
    with Session(engine()) as db:
        user = db.scalar(select(User).where(User.email == data.email))
        if not user:
            user = User(id=uuid4().hex, email=data.email, verified=False, created_at=now())
            db.add(user)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                user = db.scalar(select(User).where(User.email == data.email))
        if user and not user.verified:
            issue_link(db, user, "verify")
            db.commit()
    return Message(
        message="Si cette adresse peut être inscrite, un lien d’activation a été envoyé. "
        "Vérifiez votre boîte de réception et vos courriers indésirables."
    )


def consume_link(data: TokenPassword, kind: str):
    password_hash = hash_password(data.password)
    with Session(engine()) as db:
        # DELETE ... RETURNING makes consumption atomic, including concurrent requests.
        user_id = db.scalar(
            delete(AccountToken)
            .where(
                AccountToken.token_hash == digest(data.token),
                AccountToken.kind == kind,
                AccountToken.expires_at > now(),
            )
            .returning(AccountToken.user_id)
        )
        if not user_id:
            raise HTTPException(400, "Lien invalide ou expiré. Demandez un nouveau lien.")
        db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                password_hash=password_hash,
                verified=True,
            )
        )
        db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
        db.execute(delete(AccountToken).where(AccountToken.user_id == user_id))
        db.commit()


@router.post("/verify", response_model=Message, dependencies=[Depends(protect)])
def verify(data: TokenPassword, request: Request):
    rate_limit(request)
    consume_link(data, "verify")
    return Message(message="Compte activé. Vous pouvez maintenant vous connecter.")


@router.post("/forgot-password", response_model=Message, dependencies=[Depends(protect)])
def forgot(data: EmailInput, request: Request):
    rate_limit(request, data.email)
    with Session(engine()) as db:
        user = db.scalar(select(User).where(User.email == data.email, User.verified.is_(True)))
        if user:
            issue_link(db, user, "reset")
            db.commit()
    return Message(
        message="Si un compte correspond à cette adresse, un lien de réinitialisation "
        "a été envoyé. Vérifiez aussi vos courriers indésirables."
    )


@router.post("/reset-password", response_model=Message, dependencies=[Depends(protect)])
def reset(data: TokenPassword, request: Request):
    rate_limit(request)
    consume_link(data, "reset")
    return Message(message="Mot de passe modifié. Reconnectez-vous sur vos appareils.")


@router.post("/login", response_model=AccountResponse, dependencies=[Depends(protect)])
def login(data: Credentials, request: Request, response: Response):
    rate_limit(request, data.email)
    with Session(engine()) as db:
        user = db.scalar(select(User).where(User.email == data.email))
        valid = check_password(data.password, user.password_hash if user else None)
        if not valid or not user or not user.verified:
            raise HTTPException(
                401,
                "Adresse ou mot de passe incorrect. Si nécessaire, "
                "activez votre compte avec le lien reçu par e-mail.",
            )
        # Serialize session creation with password resets. A password verified before
        # a concurrent reset must never mint a session after that reset commits.
        unchanged = db.execute(
            update(User)
            .where(
                User.id == user.id,
                User.password_hash == user.password_hash,
                User.verified.is_(True),
            )
            .values(email=user.email)
        )
        if unchanged.rowcount != 1:
            raise HTTPException(401, "Le compte a changé. Reconnectez-vous.")
        token = secrets.token_urlsafe(32)
        db.execute(delete(LoginSession).where(LoginSession.expires_at <= now()))
        db.add(
            LoginSession(
                token_hash=digest(token),
                user_id=user.id,
                expires_at=now() + timedelta(seconds=SESSION_AGE),
            )
        )
        db.commit()
        response.set_cookie(
            COOKIE,
            token,
            max_age=SESSION_AGE,
            httponly=True,
            secure=public_url().startswith("https://"),
            samesite="strict",
            path="/",
        )
        return AccountResponse(id=user.id, email=user.email)


@router.post("/logout", status_code=204, dependencies=[Depends(protect)])
def logout(request: Request, response: Response):
    with Session(engine()) as db:
        db.execute(
            delete(LoginSession).where(
                LoginSession.token_hash == digest(request.cookies.get(COOKIE, ""))
            )
        )
        db.commit()
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        secure=public_url().startswith("https://"),
        samesite="strict",
    )
