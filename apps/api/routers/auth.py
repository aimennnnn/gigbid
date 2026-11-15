"""Sign-up, sign-in, and the user's profile (onboarding and settings)."""
from fastapi import APIRouter, Depends

from agent.marketplace_port import MarketplaceUnavailable
from apps.api.auth.users import PERSONAS, current_user, users
from apps.api.runtime import Runtime, runtime
from apps.api.schemas.models import Credentials, Me, Profile, Session

router = APIRouter(tags=["auth"])


def session(name: str, password: str) -> Session:
    return Session(token=users().login(name, password), user=name, onboarded=users().profile(name)["persona"] in PERSONAS)


@router.post("/auth/signup", response_model=Session)
def signup(body: Credentials) -> Session:
    users().add(body.username, body.password)
    return session(body.username, body.password)


@router.post("/auth/login", response_model=Session)
def login(body: Credentials) -> Session:
    return session(body.username, body.password)


@router.get("/me", response_model=Me)
async def me(user: str = Depends(current_user), rt: Runtime = Depends(runtime)) -> Me:
    try:
        connects = await rt.port_for(user).get_connects_balance()
    except MarketplaceUnavailable:
        connects = {}
    grant, balance = connects.get("weekly_grant"), connects.get("balance")
    return Me(user=user, profile=Profile(**users().profile(user)), connects_balance=balance,
              connects_spent=(grant - balance) if grant is not None and balance is not None else 0)


@router.put("/me/profile", response_model=Profile)
def set_profile(body: Profile, user: str = Depends(current_user)) -> Profile:
    return Profile(**users().set_profile(user, body.model_dump()))
