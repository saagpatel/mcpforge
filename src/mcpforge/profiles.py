"""Generation profile helpers for auth and middleware scaffolding."""

from mcpforge.models import ServerPlan

AUTH_PROFILE_ENV_VARS: dict[str, tuple[str, ...]] = {
    "api-key": ("MCPFORGE_SERVER_API_KEY",),
    "jwt": ("JWT_JWKS_URI", "JWT_ISSUER", "JWT_AUDIENCE"),
}

MIDDLEWARE_PROFILE_ENV_VARS: dict[str, tuple[str, ...]] = {
    "logging": (),
    "timing": (),
    "rate-limit": ("RATE_LIMIT_RPS", "RATE_LIMIT_BURST"),
}


def apply_generation_profiles(
    plan: ServerPlan,
    *,
    auth_profile: str = "none",
    middleware_profiles: tuple[str, ...] = (),
) -> ServerPlan:
    """Return a copy of plan with auth/middleware profile metadata applied."""
    auth = auth_profile.lower()
    middleware = tuple(profile.lower() for profile in middleware_profiles if profile)

    env_vars = list(plan.env_vars)
    for var in AUTH_PROFILE_ENV_VARS.get(auth, ()):
        if var not in env_vars:
            env_vars.append(var)
    for profile in middleware:
        for var in MIDDLEWARE_PROFILE_ENV_VARS.get(profile, ()):
            if var not in env_vars:
                env_vars.append(var)

    return plan.model_copy(
        update={
            "auth_profile": None if auth == "none" else auth,
            "middleware_profiles": list(dict.fromkeys(middleware)),
            "env_vars": env_vars,
        }
    )
