# ============================================================
# VANY PREMIUM ACCESS
# Controle central de acesso aos recursos Premium
# ============================================================

from premium_manager import premium_manager


def get_premium_access(user_id):
    """
    Retorna o estado atual de acesso Premium do utilizador.
    """

    if not user_id:
        return {
            "allowed": False,
            "plan": "free",
            "status": "inactive",
            "reason": "user_id_missing"
        }

    user = premium_manager.get_user(user_id)

    if not user:
        return {
            "allowed": False,
            "plan": "free",
            "status": "inactive",
            "reason": "user_not_found"
        }

    # Verifica se o Premium expirou
    premium_manager.check_expired(user_id)

    # Busca novamente o estado atualizado
    user = premium_manager.get_user(user_id)

    allowed = (
        user["plan"] == "premium"
        and user["premium_status"] == "active"
    )

    return {
        "allowed": allowed,
        "plan": user["plan"],
        "status": user["premium_status"],
        "premium_until": user["premium_until"],
        "user_id": user["user_id"]
    }


def require_premium(user_id):
    """
    Retorna True quando o utilizador possui Premium ativo.
    """

    access = get_premium_access(user_id)

    return access["allowed"]
