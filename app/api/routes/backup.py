"""Routes API pour la gestion des sauvegardes de la base de données.

Ces routes sont réservées à l'admin plateforme pour des raisons de sécurité.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import require_roles
from app.core.backup import backup_manager, export_metadata
from app.core.enums import RoleUtilisateur

router = APIRouter(prefix="/backup", tags=["backup"])

# ==========================================================
# Schémas Pydantic pour les réponses
# ==========================================================

class BackupInfo(BaseModel):
    """Informations sur une sauvegarde."""
    filename: str
    path: str
    size: int
    size_mb: float
    created_at: str
    is_compressed: bool


class BackupListResponse(BaseModel):
    """Réponse pour la liste des sauvegardes."""
    backups: list[BackupInfo]
    count: int
    total_size_mb: float


# ==========================================================
# Routes
# ==========================================================

@router.get("/list")
def list_backups(
    admin = Depends(require_roles(RoleUtilisateur.admin_plateforme)),
    limit: int = Query(10, ge=1, le=100, description="Nombre maximum de sauvegardes à retourner")
):
    """Liste toutes les sauvegardes disponibles.

    **Permissions :** Admin plateforme uniquement.

    **Paramètres :**
    - `limit` : Nombre maximum de sauvegardes à retourner (défaut: 10, max: 100)
    """
    backups = backup_manager.list_backups()

    # Trier par date (plus récent en premier)
    backups = sorted(backups, key=lambda x: x['created_at'], reverse=True)

    # Limiter le nombre
    if limit:
        backups = backups[:limit]

    total_size = sum(b['size_mb'] for b in backups)

    return {
        "success": True,
        "data": {
            "backups": backups,
            "count": len(backups),
            "total_size_mb": round(total_size, 2)
        }
    }


@router.post("/create")
def create_backup(
    admin = Depends(require_roles(RoleUtilisateur.admin_plateforme))
):
    """Crée une nouvelle sauvegarde manuelle de la base de données.

    **Permissions :** Admin plateforme uniquement.

    **⚠️ Attention :** La sauvegarde peut prendre quelques secondes
    selon la taille de la base de données.
    """
    try:
        backup_path = backup_manager.create_backup(compress=True)

        return {
            "success": True,
            "message": "Sauvegarde créée avec succès",
            "data": {
                "path": str(backup_path),
                "filename": backup_path.name,
                "size_mb": round(backup_path.stat().st_size / (1024 * 1024), 2),
                "created_at": backup_path.stat().st_mtime
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la sauvegarde: {str(e)}"
        ) from e


@router.post("/restore/{filename}")
def restore_backup(
    filename: str,
    confirm: bool = Query(False, description="Confirmation explicite pour la restauration"),
    admin = Depends(require_roles(RoleUtilisateur.admin_plateforme))
):
    """Restaure une sauvegarde depuis un fichier existant.

    **Permissions :** Admin plateforme uniquement.

    **⚠️ DANGER :** Cette opération écrase la base de données actuelle !
    Les données actuelles seront perdues.

    **Paramètres :**
    - `confirm` : Doit être `true` pour confirmer la restauration
    """
    # Vérification de confirmation explicite
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation requise. Veuillez passer confirm=true dans les paramètres de requête."
        )

    backup_path = backup_manager.backup_dir / filename

    if not backup_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier de sauvegarde introuvable: {filename}"
        )

    # Vérifier l'intégrité du fichier
    from app.core.backup import verify_backup
    if not verify_backup(backup_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier de sauvegarde semble corrompu."
        )

    # Restaurer la sauvegarde
    success = backup_manager.restore_backup(backup_path)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la restauration de la sauvegarde."
        )

    return {
        "success": True,
        "message": f"Sauvegarde restaurée avec succès: {filename}",
        "data": {
            "filename": filename,
            "restored_at": datetime.now().isoformat()
        }
    }


@router.get("/metadata")
def get_metadata(
    admin = Depends(require_roles(RoleUtilisateur.admin_plateforme))
):
    """Récupère les métadonnées des sauvegardes.

    **Permissions :** Admin plateforme uniquement.

    **Informations retournées :**
    - Nom de la base de données
    - Répertoire des sauvegardes
    - Nombre de sauvegardes
    - Liste des sauvegardes
    - Taille totale des sauvegardes
    """
    metadata = export_metadata()

    return {
        "success": True,
        "data": metadata
    }


@router.delete("/{filename}")
def delete_backup(
    filename: str,
    admin = Depends(require_roles(RoleUtilisateur.admin_plateforme))
):
    """Supprime une sauvegarde spécifique.

    **Permissions :** Admin plateforme uniquement.
    """
    backup_path = backup_manager.backup_dir / filename

    if not backup_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier de sauvegarde introuvable: {filename}"
        )

    try:
        # Récupérer la taille avant suppression
        size_mb = round(backup_path.stat().st_size / (1024 * 1024), 2)
        backup_path.unlink()

        return {
            "success": True,
            "message": f"Sauvegarde supprimée avec succès: {filename}",
            "data": {
                "filename": filename,
                "size_mb": size_mb
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression de la sauvegarde: {str(e)}"
        ) from e


@router.post("/cleanup")
def cleanup_backups(
    keep_count: int = Query(7, ge=1, le=30, description="Nombre de sauvegardes à conserver"),
    admin = Depends(require_roles(RoleUtilisateur.admin_plateforme))
):
    """Nettoie les anciennes sauvegardes en conservant les N plus récentes.

    **Permissions :** Admin plateforme uniquement.

    **Paramètres :**
    - `keep_count` : Nombre de sauvegardes à conserver (défaut: 7, max: 30)
    """
    try:
        backup_manager.cleanup_old_backups(keep_count=keep_count)

        return {
            "success": True,
            "message": f"Nettoyage effectué. {keep_count} sauvegardes les plus récentes conservées.",
            "data": {
                "keep_count": keep_count,
                "remaining_backups": len(backup_manager.list_backups())
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du nettoyage: {str(e)}"
        ) from e
