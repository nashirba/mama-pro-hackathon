"""The single place that decides how a community author is named. Never show the phone."""


def is_specialist(user) -> bool:
    return hasattr(user, "specialist_profile")


def author_name(user) -> str:
    if is_specialist(user):
        return user.specialist_profile.display_name
    return user.display_name or ""


def needs_nickname(user) -> bool:
    return not is_specialist(user) and not user.display_name
