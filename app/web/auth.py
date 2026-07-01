from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app import security
from app.web._render import render
from app.api import optional_user
from app.validation import validate_signup

router = APIRouter()


@router.get("/login")
def login_page(request: Request, user: User | None = Depends(optional_user)):
    return render(request, "login.html", {"error": None}, user=user)


@router.post("/login")
def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    ident = identifier.strip()
    user = db.scalar(
        select(User).where((User.email == ident) | (User.username == ident))
    )
    if user is None or not security.verify_password(password, user.password_hash):
        resp = render(
            request,
            "login.html",
            {"error": "Those credentials did not match. Please try again."},
        )
        resp.status_code = 401
        return resp
    request.session["uid"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/signup")
def signup_page(request: Request, user: User | None = Depends(optional_user)):
    return render(request, "signup.html", {"error": None}, user=user)


@router.post("/signup")
def signup_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    try:
        validate_signup(username, email, password)
    except ValueError as e:
        resp = render(request, "signup.html", {"error": str(e)})
        resp.status_code = 400
        return resp
    exists = db.scalar(
        select(User).where((User.username == username) | (User.email == email))
    )
    if exists is not None:
        resp = render(
            request,
            "signup.html",
            {"error": "That username or email is already taken."},
        )
        resp.status_code = 400
        return resp
    user = User(
        username=username,
        email=email,
        password_hash=security.hash_password(password),
    )
    db.add(user)
    db.commit()
    request.session["uid"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
