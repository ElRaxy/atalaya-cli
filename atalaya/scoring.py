"""Scoring de ofertas contra el perfil del usuario."""

from __future__ import annotations

from atalaya.models import Offer, Profile, ScoreBreakdown

_WEIGHT_STACK = 0.50
_WEIGHT_REMOTE = 0.25
_WEIGHT_SENIORITY = 0.15
_WEIGHT_LANGUAGE = 0.10

_SENIORITY_ORDER = {"intern": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4, "staff": 5}
_LANG_EUROPEAN = {"en", "es", "ca", "va", "pt", "it", "fr", "de"}


def _normalize(values: list[str]) -> set[str]:
    return {v.strip().lower() for v in values if v and v.strip()}


def _stack_score(offer: Offer, profile: Profile) -> int:
    offer_stack = _normalize(offer.stack)
    if not offer_stack:
        return 0
    core = _normalize(profile.stack_core)
    extra = _normalize(profile.stack_extra)
    combined = core | extra
    if not combined:
        return 0
    intersection = offer_stack & combined
    union = offer_stack | combined
    jaccard = round(100 * len(intersection) / len(union)) if union else 0
    bonus = 20 if (offer_stack & core) else 0
    return min(100, jaccard + bonus)


def _remote_score(offer: Offer, profile: Profile) -> int:
    if offer.remote:
        return 100
    modes = _normalize(profile.modes)
    if "remote" in modes and not offer.remote:
        return 0
    return 0


def _seniority_score(offer: Offer, profile: Profile) -> int:
    if not offer.seniority:
        return 60
    offer_level = _SENIORITY_ORDER.get(offer.seniority.strip().lower())
    profile_level = _SENIORITY_ORDER.get(profile.seniority.strip().lower())
    if offer_level is None or profile_level is None:
        return 60
    diff = abs(offer_level - profile_level)
    if diff == 0:
        return 100
    if diff == 1:
        return 60
    return 0


def _language_score(offer: Offer, profile: Profile) -> int:
    profile_langs = _normalize(profile.languages)
    text = f"{offer.title} {offer.description}".lower()
    if not text.strip():
        return 70
    spanish_hints = (" es ", "espanol", "español", "castellano", " spain", "espana", "españa")
    if any(lang in profile_langs for lang in ("es", "ca", "va")) and any(
        word in text for word in spanish_hints
    ):
        return 100
    if "en" in profile_langs and any(w in text for w in (" en ", "english", "ingles", "inglés")):
        return 70
    if any(lang in _LANG_EUROPEAN for lang in profile_langs):
        return 70
    return 30


def score_offer(offer: Offer, profile: Profile) -> ScoreBreakdown:
    stack = _stack_score(offer, profile)
    remote = _remote_score(offer, profile)
    seniority = _seniority_score(offer, profile)
    language = _language_score(offer, profile)
    total = round(
        stack * _WEIGHT_STACK
        + remote * _WEIGHT_REMOTE
        + seniority * _WEIGHT_SENIORITY
        + language * _WEIGHT_LANGUAGE
    )
    total = max(0, min(100, total))
    return ScoreBreakdown(
        total=total,
        stack_match=stack,
        remote_match=remote,
        seniority_match=seniority,
        language_match=language,
    )
