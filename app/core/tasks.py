"""Tâches asynchrones (Celery).

Ce module centralise les traitements de fond pour ne pas bloquer les requêtes
HTTP (ex: envoi d'email de vérification).
"""

import logging
from typing import Any

from celery import Celery
from celery.result import AsyncResult
from celery.signals import task_failure, task_retry, task_success

from app.core.config import settings
from app.core.emailing import (
    envoyer_email_bienvenue,
    envoyer_email_offre_envoyee,
    envoyer_email_reset_password,
    envoyer_email_verification,
)

logger = logging.getLogger("talentia.tasks")

# ==========================================================
# Configuration Celery
# ==========================================================

celery_app = Celery(
    "talentia",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Sérialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Résultats
    task_ignore_result=False,
    result_expires=3600,  # 1 heure

    # Timeouts
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes

    # Retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Concurrency
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Broker
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)

# ==========================================================
# Signaux Celery
# ==========================================================

@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Logge les succès de tâches."""
    logger.info(f"✅ Task completed: {sender.name} - Result: {result}")


@task_failure.connect
def task_failure_handler(sender=None, exception=None, **kwargs):
    """Logge les échecs de tâches."""
    logger.error(f"❌ Task failed: {sender.name} - Error: {exception}")


@task_retry.connect
def task_retry_handler(sender=None, reason=None, **kwargs):
    """Logge les reprises de tâches."""
    logger.warning(f"🔄 Task retry: {sender.name} - Reason: {reason}")


# ==========================================================
# Tâches d'email
# ==========================================================

@celery_app.task(
    name="talentia.send_verification_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_verification_email_async(self, email: str, nom: str, token: str) -> bool:
    """Envoi d'email de vérification en arrière-plan via worker Celery.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        token: Jeton de vérification
        
    Returns:
        bool: True si l'email a été envoyé
    """
    try:
        result = envoyer_email_verification(email, nom, token)
        logger.info(f"📧 Verification email sent to {email}")
        return result
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        # Retry avec backoff
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return False


@celery_app.task(
    name="talentia.send_welcome_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_welcome_email_async(self, email: str, nom: str) -> bool:
    """Envoi d'email de bienvenue en arrière-plan.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        
    Returns:
        bool: True si l'email a été envoyé
    """
    try:
        result = envoyer_email_bienvenue(email, nom)
        logger.info(f"📧 Welcome email sent to {email}")
        return result
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {e}")
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return False


@celery_app.task(
    name="talentia.send_reset_password_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_reset_password_email_async(self, email: str, nom: str, token: str) -> bool:
    """Envoi d'email de réinitialisation de mot de passe.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        token: Jeton de réinitialisation
        
    Returns:
        bool: True si l'email a été envoyé
    """
    try:
        result = envoyer_email_reset_password(email, nom, token)
        logger.info(f"📧 Reset password email sent to {email}")
        return result
    except Exception as e:
        logger.error(f"Failed to send reset password email to {email}: {e}")
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return False


@celery_app.task(
    name="talentia.send_offre_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_offre_email_async(self, email: str, nom: str, offre_titre: str) -> bool:
    """Envoi d'email de notification d'offre.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        offre_titre: Titre de l'offre
        
    Returns:
        bool: True si l'email a été envoyé
    """
    try:
        result = envoyer_email_offre_envoyee(email, nom, offre_titre)
        logger.info(f"📧 Offre email sent to {email} for {offre_titre}")
        return result
    except Exception as e:
        logger.error(f"Failed to send offre email to {email}: {e}")
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return False


# ==========================================================
# Tâches de notification
# ==========================================================

@celery_app.task(name="talentia.notify_user")
def notify_user_async(user_id: str, notification_type: str, data: dict[str, Any]) -> bool:
    """Tâche pour envoyer des notifications aux utilisateurs.
    
    Args:
        user_id: ID de l'utilisateur
        notification_type: Type de notification
        data: Données de la notification
        
    Returns:
        bool: True si la notification a été envoyée
    """
    try:
        # À implémenter avec un système de notifications
        logger.info(f"🔔 Notification sent to {user_id}: {notification_type}")
        return True
    except Exception as e:
        logger.error(f"Failed to send notification to {user_id}: {e}")
        return False


@celery_app.task(name="talentia.process_candidature")
def process_candidature_async(candidature_id: str) -> bool:
    """Tâche pour traiter une candidature (matching IA, etc.).
    
    Args:
        candidature_id: ID de la candidature
        
    Returns:
        bool: True si le traitement a réussi
    """
    try:
        # À implémenter avec le matching IA
        logger.info(f"🤖 Processing candidature: {candidature_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to process candidature {candidature_id}: {e}")
        return False


# ==========================================================
# Tâches de nettoyage
# ==========================================================

@celery_app.task(name="talentia.cleanup_expired_tokens")
def cleanup_expired_tokens_async() -> int:
    """Tâche de nettoyage des tokens expirés.
    
    Returns:
        int: Nombre de tokens supprimés
    """
    try:
        # À implémenter avec le modèle de tokens
        logger.info("🧹 Cleaning up expired tokens")
        return 0
    except Exception as e:
        logger.error(f"Failed to cleanup expired tokens: {e}")
        return 0


@celery_app.task(name="talentia.cleanup_old_backups")
def cleanup_old_backups_async() -> int:
    """Tâche de nettoyage des anciennes sauvegardes.
    
    Returns:
        int: Nombre de sauvegardes supprimées
    """
    try:
        from app.core.backup import backup_manager
        deleted = backup_manager.cleanup_old_backups()
        logger.info(f"🧹 Cleaned up {deleted} old backups")
        return deleted
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")
        return 0


# ==========================================================
# Fonctions d'enfilement (avec fallback)
# ==========================================================

def queue_verification_email(email: str, nom: str, token: str) -> bool:
    """Enfile un envoi d'email de vérification.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        token: Jeton de vérification
        
    Returns:
        bool: True si la tâche a été enfilée ou exécutée
    """
    try:
        send_verification_email_async.delay(email, nom, token)
        logger.info(f"📧 Verification email queued for {email}")
        return True
    except Exception as e:
        logger.exception(f"❌ Impossible d'enfiler la tâche Celery: {e}")
        # Fallback synchrone
        logger.info(f"📧 Fallback: sending verification email synchronously to {email}")
        return envoyer_email_verification(email, nom, token)


def queue_welcome_email(email: str, nom: str) -> bool:
    """Enfile un envoi d'email de bienvenue.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        
    Returns:
        bool: True si la tâche a été enfilée ou exécutée
    """
    try:
        send_welcome_email_async.delay(email, nom)
        logger.info(f"📧 Welcome email queued for {email}")
        return True
    except Exception as e:
        logger.exception(f"❌ Impossible d'enfiler la tâche Celery: {e}")
        return envoyer_email_bienvenue(email, nom)


def queue_reset_password_email(email: str, nom: str, token: str) -> bool:
    """Enfile un envoi d'email de réinitialisation.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        token: Jeton de réinitialisation
        
    Returns:
        bool: True si la tâche a été enfilée ou exécutée
    """
    try:
        send_reset_password_email_async.delay(email, nom, token)
        logger.info(f"📧 Reset password email queued for {email}")
        return True
    except Exception as e:
        logger.exception(f"❌ Impossible d'enfiler la tâche Celery: {e}")
        return envoyer_email_reset_password(email, nom, token)


def queue_offre_email(email: str, nom: str, offre_titre: str) -> bool:
    """Enfile un envoi d'email d'offre.
    
    Args:
        email: Destinataire
        nom: Nom du destinataire
        offre_titre: Titre de l'offre
        
    Returns:
        bool: True si la tâche a été enfilée ou exécutée
    """
    try:
        send_offre_email_async.delay(email, nom, offre_titre)
        logger.info(f"📧 Offre email queued for {email}")
        return True
    except Exception as e:
        logger.exception(f"❌ Impossible d'enfiler la tâche Celery: {e}")
        return envoyer_email_offre_envoyee(email, nom, offre_titre)


# ==========================================================
# Monitoring
# ==========================================================

def get_task_status(task_id: str) -> dict[str, Any]:
    """Récupère le statut d'une tâche.
    
    Args:
        task_id: ID de la tâche
        
    Returns:
        dict: Statut de la tâche
    """
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
    }


def get_active_tasks() -> list:
    """Récupère les tâches actives.
    
    Returns:
        list: Liste des tâches actives
    """
    inspect = celery_app.control.inspect()
    return inspect.active() if inspect else []


def get_scheduled_tasks() -> list:
    """Récupère les tâches planifiées.
    
    Returns:
        list: Liste des tâches planifiées
    """
    inspect = celery_app.control.inspect()
    return inspect.scheduled() if inspect else []
