"""Envoi d'emails transactionnels (vérification d'inscription).

En développement, si aucun SMTP n'est configuré (`smtp_host` vide dans les
réglages), l'email n'est pas réellement expédié : le lien est journalisé, ce
qui permet de tester tout le flux (inscription → vérification) sans serveur
mail. En production, renseigner `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD`
dans `.env` pour un envoi réel.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("talentia.emailing")


# ==========================================================
# Templates HTML (intégrés pour l'instant)
# ==========================================================

TEMPLATE_VERIFICATION_EMAIL = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; }
        .button { display: inline-block; background: #4F46E5; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }
        .footer { text-align: center; font-size: 12px; color: #6b7280; margin-top: 20px; }
        .warning { color: #6b7280; font-size: 14px; border-top: 1px solid #e5e7eb; padding-top: 15px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0;">🎯 TalentIA</h1>
    </div>
    <div class="content">
        <h2>Bonjour {nom} !</h2>
        <p>Merci de vous être inscrit sur <strong>TalentIA</strong>. Pour finaliser votre inscription, veuillez confirmer votre adresse email.</p>
        <p style="text-align: center;">
            <a href="{lien}" class="button">✅ Confirmer mon email</a>
        </p>
        <p>Ou copiez ce lien dans votre navigateur :</p>
        <p style="background: #f3f4f6; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 14px;">
            {lien}
        </p>
        <p><strong>⏰ Ce lien expire dans {expiration} minutes.</strong></p>
        <div class="warning">
            <p>Si vous n'êtes pas à l'origine de cette inscription, vous pouvez ignorer cet email.</p>
        </div>
    </div>
    <div class="footer">
        <p>© TalentIA - Plateforme de recrutement IA</p>
    </div>
</body>
</html>
"""

TEMPLATE_RESET_PASSWORD = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; }
        .button { display: inline-block; background: #4F46E5; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }
        .footer { text-align: center; font-size: 12px; color: #6b7280; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0;">🔐 Réinitialisation du mot de passe</h1>
    </div>
    <div class="content">
        <h2>Bonjour {nom} !</h2>
        <p>Nous avons reçu une demande de réinitialisation de votre mot de passe sur <strong>TalentIA</strong>.</p>
        <p style="text-align: center;">
            <a href="{lien}" class="button">🔄 Réinitialiser mon mot de passe</a>
        </p>
        <p><strong>⏰ Ce lien expire dans {expiration} minutes.</strong></p>
        <p style="color: #6b7280; font-size: 14px;">
            Si vous n'avez pas demandé de réinitialisation, ignorez cet email.
        </p>
    </div>
    <div class="footer">
        <p>© TalentIA - Plateforme de recrutement IA</p>
    </div>
</body>
</html>
"""


# ==========================================================
# Fonctions d'envoi
# ==========================================================

def _envoyer(
    destinataire: str,
    sujet: str,
    corps_texte: str,
    corps_html: str,
    reply_to: str | None = None,
) -> bool:
    """Envoie un email avec les formats texte et HTML.
    
    Args:
        destinataire: Adresse email du destinataire
        sujet: Sujet de l'email
        corps_texte: Version texte du message
        corps_html: Version HTML du message
        reply_to: Adresse de réponse (optionnel)
        
    Returns:
        bool: True si l'email a été envoyé ou loggé avec succès
    """
    # Mode développement : log seulement
    if not settings.smtp_configured:
        logger.info(
            "[emailing:dev] ⚠️ Aucun SMTP configuré — email non envoyé.\n"
            "📧 À: %s\n📝 Sujet: %s\n📄 Contenu:\n%s",
            destinataire,
            sujet,
            corps_texte,
        )
        return True

    try:
        # Créer le message
        message = MIMEMultipart("alternative")
        message["Subject"] = sujet
        message["From"] = settings.smtp_from
        message["To"] = destinataire
        message["X-Mailer"] = "TalentIA API"

        if reply_to:
            message["Reply-To"] = reply_to

        # Ajouter les versions texte et HTML
        part_text = MIMEText(corps_texte, "plain", "utf-8")
        part_html = MIMEText(corps_html, "html", "utf-8")
        message.attach(part_text)
        message.attach(part_html)

        # Envoyer via SMTP
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)

        logger.info(f"✅ Email envoyé avec succès à {destinataire}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ Erreur d'authentification SMTP: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"❌ Erreur SMTP: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi de l'email: {e}")
        return False


# ==========================================================
# Templates d'emails
# ==========================================================

def envoyer_email_verification(destinataire: str, nom: str, token: str) -> bool:
    """Envoie le lien de confirmation d'adresse email à l'inscription.
    
    Args:
        destinataire: Adresse email du destinataire
        nom: Nom du destinataire
        token: Jeton de vérification
        
    Returns:
        bool: True si l'email a été envoyé avec succès
    """
    lien = f"{settings.frontend_url}/verify-email?token={token}"
    expiration = settings.email_verification_expire_minutes

    sujet = "Confirmez votre adresse email — TalentIA"

    texte = (
        f"Bonjour {nom},\n\n"
        f"Merci de confirmer votre adresse email en ouvrant ce lien :\n{lien}\n\n"
        f"Ce lien expire dans {expiration} minutes.\n"
        "Si vous n'êtes pas à l'origine de cette inscription, ignorez cet email.\n\n"
        "---\n"
        "TalentIA - Plateforme de recrutement IA"
    )

    html = TEMPLATE_VERIFICATION_EMAIL.format(
        nom=nom,
        lien=lien,
        expiration=expiration,
    )

    return _envoyer(destinataire, sujet, texte, html)


def envoyer_email_bienvenue(destinataire: str, nom: str) -> bool:
    """Envoie un email de bienvenue après la vérification.
    
    Args:
        destinataire: Adresse email du destinataire
        nom: Nom du destinataire
        
    Returns:
        bool: True si l'email a été envoyé avec succès
    """
    sujet = "Bienvenue sur TalentIA !"

    texte = (
        f"Bonjour {nom},\n\n"
        f"Bienvenue sur TalentIA ! Votre compte a été activé avec succès.\n\n"
        f"Vous pouvez maintenant :\n"
        f"- Explorer les offres d'emploi\n"
        f"- Postuler aux offres qui vous intéressent\n"
        f"- Suivre l'état de vos candidatures\n\n"
        f"L'équipe TalentIA vous souhaite une excellente expérience.\n\n"
        "---\n"
        "TalentIA - Plateforme de recrutement IA"
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0;">🎉 Bienvenue sur TalentIA</h1>
        </div>
        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb;">
            <h2>Bonjour {nom} !</h2>
            <p>Votre compte a été activé avec succès.</p>
            <p>Vous pouvez maintenant :</p>
            <ul>
                <li>🔍 Explorer les offres d'emploi</li>
                <li>📝 Postuler aux offres qui vous intéressent</li>
                <li>📊 Suivre l'état de vos candidatures</li>
            </ul>
            <p>L'équipe TalentIA vous souhaite une excellente expérience.</p>
        </div>
        <div style="text-align: center; font-size: 12px; color: #6b7280; margin-top: 20px;">
            <p>© TalentIA - Plateforme de recrutement IA</p>
        </div>
    </body>
    </html>
    """

    return _envoyer(destinataire, sujet, texte, html)


def envoyer_email_reset_password(destinataire: str, nom: str, token: str) -> bool:
    """Envoie un email de réinitialisation de mot de passe.
    
    Args:
        destinataire: Adresse email du destinataire
        nom: Nom du destinataire
        token: Jeton de réinitialisation
        
    Returns:
        bool: True si l'email a été envoyé avec succès
    """
    lien = f"{settings.frontend_url}/reset-password?token={token}"
    expiration = settings.email_verification_expire_minutes

    sujet = "Réinitialisation de votre mot de passe — TalentIA"

    texte = (
        f"Bonjour {nom},\n\n"
        f"Nous avons reçu une demande de réinitialisation de votre mot de passe sur TalentIA.\n\n"
        f"Cliquez sur ce lien pour réinitialiser votre mot de passe :\n{lien}\n\n"
        f"Ce lien expire dans {expiration} minutes.\n"
        "Si vous n'avez pas demandé de réinitialisation, ignorez cet email.\n\n"
        "---\n"
        "TalentIA - Plateforme de recrutement IA"
    )

    html = TEMPLATE_RESET_PASSWORD.format(
        nom=nom,
        lien=lien,
        expiration=expiration,
    )

    return _envoyer(destinataire, sujet, texte, html)


def envoyer_email_offre_envoyee(destinataire: str, nom: str, offre_titre: str) -> bool:
    """Envoie une notification quand une offre est envoyée à un candidat.
    
    Args:
        destinataire: Adresse email du destinataire
        nom: Nom du destinataire
        offre_titre: Titre de l'offre
        
    Returns:
        bool: True si l'email a été envoyé avec succès
    """
    sujet = f"Offre d'emploi envoyée — {offre_titre}"

    texte = (
        f"Bonjour {nom},\n\n"
        f"Vous avez reçu une offre d'emploi pour le poste de {offre_titre}.\n\n"
        f"Connectez-vous à votre espace TalentIA pour consulter et répondre à cette offre.\n\n"
        "---\n"
        "TalentIA - Plateforme de recrutement IA"
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0;">📨 Offre d'emploi</h1>
        </div>
        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb;">
            <h2>Bonjour {nom} !</h2>
            <p>Vous avez reçu une offre d'emploi pour le poste de <strong>{offre_titre}</strong>.</p>
            <p>Connectez-vous à votre espace TalentIA pour consulter et répondre à cette offre.</p>
            <p style="text-align: center; margin-top: 20px;">
                <a href="{settings.frontend_url}" style="display: inline-block; background: #4F46E5; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px;">
                    🔗 Accéder à mon espace
                </a>
            </p>
        </div>
        <div style="text-align: center; font-size: 12px; color: #6b7280; margin-top: 20px;">
            <p>© TalentIA - Plateforme de recrutement IA</p>
        </div>
    </body>
    </html>
    """

    return _envoyer(destinataire, sujet, texte, html)
