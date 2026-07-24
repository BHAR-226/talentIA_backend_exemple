"""Système de permissions granulaire."""

import uuid
from collections.abc import Callable
from functools import wraps
from inspect import iscoroutinefunction

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.enums import RoleUtilisateur
from app.models.utilisateur import Utilisateur

# ==========================================================
# Définition des permissions
# ==========================================================

class Permission:
    """Définition d'une permission."""

    def __init__(self, resource: str, action: str, description: str = ""):
        self.resource = resource
        self.action = action
        self.description = description

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"

    def __eq__(self, other) -> bool:
        if isinstance(other, Permission):
            return self.resource == other.resource and self.action == other.action
        return False

    def __hash__(self) -> int:
        return hash(str(self))


# ==========================================================
# Définition des rôles et permissions
# ==========================================================

# Permissions prédéfinies
PERMISSIONS = {
    # Offres
    "offre:create": Permission("offre", "create", "Créer une offre"),
    "offre:read": Permission("offre", "read", "Lire une offre"),
    "offre:update": Permission("offre", "update", "Modifier une offre"),
    "offre:delete": Permission("offre", "delete", "Supprimer une offre"),
    "offre:publish": Permission("offre", "publish", "Publier une offre"),
    "offre:archive": Permission("offre", "archive", "Archiver une offre"),

    # Campagnes
    "campagne:create": Permission("campagne", "create", "Créer une campagne"),
    "campagne:read": Permission("campagne", "read", "Lire une campagne"),
    "campagne:update": Permission("campagne", "update", "Modifier une campagne"),
    "campagne:delete": Permission("campagne", "delete", "Supprimer une campagne"),

    # Candidatures
    "candidature:read": Permission("candidature", "read", "Lire une candidature"),
    "candidature:evaluate": Permission("candidature", "evaluate", "Évaluer une candidature"),
    "candidature:update": Permission("candidature", "update", "Modifier une candidature"),
    "candidature:delete": Permission("candidature", "delete", "Supprimer une candidature"),

    # Utilisateurs
    "user:read": Permission("user", "read", "Lire un utilisateur"),
    "user:create": Permission("user", "create", "Créer un utilisateur"),
    "user:update": Permission("user", "update", "Modifier un utilisateur"),
    "user:delete": Permission("user", "delete", "Supprimer un utilisateur"),
    "user:promote": Permission("user", "promote", "Promouvoir un utilisateur"),

    # Entreprises
    "entreprise:read": Permission("entreprise", "read", "Lire une entreprise"),
    "entreprise:update": Permission("entreprise", "update", "Modifier une entreprise"),
    "entreprise:suspend": Permission("entreprise", "suspend", "Suspendre une entreprise"),

    # Abonnements
    "abonnement:read": Permission("abonnement", "read", "Lire un abonnement"),
    "abonnement:update": Permission("abonnement", "update", "Modifier un abonnement"),

    # Admin
    "admin:stats": Permission("admin", "stats", "Voir les statistiques"),
    "admin:manage": Permission("admin", "manage", "Gestion administrative"),
}

# Permissions par rôle
ROLE_PERMISSIONS: dict[RoleUtilisateur, set[str]] = {
    RoleUtilisateur.admin_plateforme: {
        # Toutes les permissions
        *PERMISSIONS.keys(),
    },
    RoleUtilisateur.admin_rh: {
        "offre:create", "offre:read", "offre:update", "offre:delete",
        "offre:publish", "offre:archive",
        "campagne:create", "campagne:read", "campagne:update", "campagne:delete",
        "candidature:read", "candidature:evaluate", "candidature:update",
        "user:read", "user:create", "user:update", "user:delete", "user:promote",
        "entreprise:read", "entreprise:update",
        "abonnement:read", "abonnement:update",
        "admin:stats",
    },
    RoleUtilisateur.recruteur: {
        "offre:create", "offre:read", "offre:update",
        "offre:publish", "offre:archive",
        "campagne:create", "campagne:read", "campagne:update",
        "candidature:read", "candidature:evaluate", "candidature:update",
        "user:read",
        "entreprise:read",
        "abonnement:read",
    },
    RoleUtilisateur.evaluateur_technique: {
        "offre:read",
        "candidature:read", "candidature:evaluate",
        "user:read",
        "entreprise:read",
        "abonnement:read",
    },
}


# ==========================================================
# PermissionChecker
# ==========================================================

class PermissionChecker:
    """Vérificateur de permissions granulaire."""

    def __init__(self, user: Utilisateur):
        """Initialise le vérificateur avec un utilisateur.
        
        Args:
            user: Utilisateur à vérifier
        """
        self.user = user
        self._permissions = ROLE_PERMISSIONS.get(user.role, set())

    def has_permission(self, permission: str) -> bool:
        """Vérifie si l'utilisateur a une permission spécifique.
        
        Args:
            permission: Permission à vérifier (format: "resource:action")
            
        Returns:
            bool: True si l'utilisateur a la permission
        """
        # Admin plateforme a tous les droits
        if self.user.role == RoleUtilisateur.admin_plateforme:
            return True

        return permission in self._permissions

    def can(self, resource: str, action: str, resource_id: uuid.UUID | None = None) -> bool:
        """Vérifie si l'utilisateur peut effectuer une action sur une ressource.
        
        Args:
            resource: Type de ressource (offre, candidature, etc.)
            action: Action à effectuer (read, write, delete, etc.)
            resource_id: ID de la ressource (optionnel)
            
        Returns:
            bool: True si l'utilisateur a la permission
        """
        permission = f"{resource}:{action}"
        return self.has_permission(permission)

    def check(self, resource: str, action: str, resource_id: uuid.UUID | None = None) -> bool:
        """Vérifie la permission et lève une exception si refusée.
        
        Args:
            resource: Type de ressource
            action: Action à effectuer
            resource_id: ID de la ressource (optionnel)
            
        Returns:
            bool: True si autorisé
            
        Raises:
            HTTPException: 403 si la permission est refusée
        """
        if not self.can(resource, action, resource_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission refusée: {action} sur {resource}"
            )
        return True

    def check_permission(self, permission: str) -> bool:
        """Vérifie une permission spécifique.
        
        Args:
            permission: Permission au format "resource:action"
            
        Returns:
            bool: True si autorisé
        """
        if not self.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission refusée: {permission}"
            )
        return True

    def get_permissions(self) -> list[str]:
        """Retourne la liste des permissions de l'utilisateur."""
        return list(self._permissions)

    def get_allowed_resources(self) -> dict[str, list[str]]:
        """Retourne les ressources et actions autorisées.
        
        Returns:
            Dict: {resource: [actions]}
        """
        result = {}
        for perm in self._permissions:
            if ':' in perm:
                resource, action = perm.split(':', 1)
                if resource not in result:
                    result[resource] = []
                result[resource].append(action)
        return result


# ==========================================================
# Décorateur pour les permissions
# ==========================================================

def require_permission(permission: str):
    """Décorateur pour vérifier une permission spécifique.
    
    Usage:
        @router.post("/offres")
        @require_permission("offre:create")
        def create_offre(user: Utilisateur = Depends(get_current_user)):
            ...
    
    Args:
        permission: Permission requise (format: "resource:action")
    """
    def decorator(func: Callable):
        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                user = _find_user_in_args(args, kwargs)

                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Utilisateur non authentifié"
                    )

                checker = PermissionChecker(user)
                checker.check_permission(permission)

                return await func(*args, **kwargs)
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = _find_user_in_args(args, kwargs)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Utilisateur non authentifié"
                )

            checker = PermissionChecker(user)
            checker.check_permission(permission)

            return func(*args, **kwargs)
        return sync_wrapper
    return decorator


def require_permissions(resource: str, action: str):
    """Décorateur pour vérifier une permission sur une ressource.
    
    Usage:
        @router.put("/offres/{offre_id}")
        @require_permissions("offre", "update")
        def update_offre(...):
            ...
    
    Args:
        resource: Type de ressource
        action: Action à effectuer
    """
    def decorator(func: Callable):
        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                user = _find_user_in_args(args, kwargs)

                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Utilisateur non authentifié"
                    )

                checker = PermissionChecker(user)
                checker.check(resource, action)

                return await func(*args, **kwargs)
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = _find_user_in_args(args, kwargs)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Utilisateur non authentifié"
                )

            checker = PermissionChecker(user)
            checker.check(resource, action)

            return func(*args, **kwargs)
        return sync_wrapper
    return decorator


def _find_user_in_args(args: tuple, kwargs: dict) -> Utilisateur | None:
    """Trouve l'utilisateur dans les arguments de la fonction."""
    # Chercher dans les arguments positionnels
    for arg in args:
        if isinstance(arg, Utilisateur):
            return arg

    # Chercher dans les arguments nommés
    if 'user' in kwargs:
        return kwargs['user']
    if 'current_user' in kwargs:
        return kwargs['current_user']

    return None


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def get_all_permissions() -> dict[str, Permission]:
    """Retourne toutes les permissions définies."""
    return PERMISSIONS


def get_role_permissions(role: RoleUtilisateur) -> set[str]:
    """Retourne les permissions d'un rôle."""
    return ROLE_PERMISSIONS.get(role, set())


def get_permission_description(permission: str) -> str:
    """Retourne la description d'une permission."""
    if permission in PERMISSIONS:
        return PERMISSIONS[permission].description
    return f"Permission: {permission}"


def has_permission(user: Utilisateur, permission: str) -> bool:
    """Fonction utilitaire pour vérifier une permission.
    
    Args:
        user: Utilisateur à vérifier
        permission: Permission à vérifier
        
    Returns:
        bool: True si l'utilisateur a la permission
    """
    checker = PermissionChecker(user)
    return checker.has_permission(permission)


# ==========================================================
# Middleware pour injecter le checker dans les requêtes
# ==========================================================

class PermissionMiddleware:
    """Middleware pour ajouter le PermissionChecker à la requête."""

    async def __call__(self, request, call_next):
        # Le checker sera ajouté via une dépendance
        response = await call_next(request)
        return response


# ==========================================================
# Dépendance FastAPI pour le PermissionChecker
# ==========================================================

def get_permission_checker(user: Utilisateur = Depends(get_current_user)) -> PermissionChecker:
    """Dépendance FastAPI pour obtenir un PermissionChecker.
    
    Usage:
        @router.get("/admin")
        def admin_route(checker: PermissionChecker = Depends(get_permission_checker)):
            checker.check("admin", "stats")
            ...
    """
    return PermissionChecker(user)
