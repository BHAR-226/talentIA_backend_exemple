"""Sauvegarde automatique de la base de données."""

import asyncio
import gzip
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("talentia.backup")


class DatabaseBackup:
    """Gestionnaire de sauvegarde de la base de données PostgreSQL."""

    def __init__(self, backup_dir: str | None = None):
        """Initialise le gestionnaire de sauvegarde.
        
        Args:
            backup_dir: Répertoire de sauvegarde (défaut: config)
        """
        self.backup_dir = Path(backup_dir or settings.backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Extraire les informations de connexion depuis l'URL
        self.db_url = settings.database_url
        self._parse_db_url()

        # Configuration
        self.keep_count = settings.backup_keep_count
        self.compression = settings.backup_compression

    def _parse_db_url(self) -> None:
        """Parse l'URL de la base de données."""
        # Format: postgresql+psycopg://user:password@host:port/database
        url = self.db_url.replace("postgresql+psycopg://", "")
        url = url.replace("postgresql://", "")

        parts = url.split('@')
        if len(parts) == 2:
            auth = parts[0].split(':')
            self.user = auth[0]
            self.password = auth[1] if len(auth) > 1 else ''

            host_port_db = parts[1].split('/')
            host_port = host_port_db[0].split(':')
            self.host = host_port[0]
            self.port = host_port[1] if len(host_port) > 1 else '5432'
            self.database = host_port_db[1] if len(host_port_db) > 1 else ''
        else:
            # Format simplifié pour le développement
            self.user = 'postgres'
            self.password = ''
            self.host = 'localhost'
            self.port = '5432'
            self.database = url.split('/')[-1] if '/' in url else 'talentia'

    def create_backup(self, compress: bool | None = None) -> Path:
        """Crée une sauvegarde de la base de données.
        
        Args:
            compress: Compresser la sauvegarde (défaut: config)
            
        Returns:
            Path: Chemin vers le fichier de sauvegarde créé
        """
        if compress is None:
            compress = self.compression

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{self.database}_{timestamp}"

        if compress:
            filename += ".sql.gz"
            backup_path = self.backup_dir / filename
            self._backup_with_compression(backup_path)
        else:
            filename += ".sql"
            backup_path = self.backup_dir / filename
            self._backup_without_compression(backup_path)

        # Vérifier l'intégrité de la sauvegarde
        if not verify_backup(backup_path):
            logger.error(f"⚠️ La sauvegarde semble corrompue: {backup_path}")
            raise RuntimeError(f"Backup verification failed: {backup_path}")

        logger.info(f"✅ Sauvegarde créée: {backup_path} ({backup_path.stat().st_size / (1024*1024):.2f} MB)")
        return backup_path

    def _backup_with_compression(self, output_path: Path) -> None:
        """Crée une sauvegarde compressée."""
        cmd = [
            'pg_dump',
            '-h', self.host,
            '-p', self.port,
            '-U', self.user,
            '-d', self.database,
            '-F', 'c',  # Format personnalisé (compressé)
            '-f', str(output_path),
        ]

        env = os.environ.copy()
        if self.password:
            env['PGPASSWORD'] = self.password

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stderr:
                logger.warning(f"pg_dump warnings: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {e.stderr}")
            raise

    def _backup_without_compression(self, output_path: Path) -> None:
        """Crée une sauvegarde non compressée."""
        cmd = [
            'pg_dump',
            '-h', self.host,
            '-p', self.port,
            '-U', self.user,
            '-d', self.database,
            '--clean',
            '--if-exists',
            '-f', str(output_path),
        ]

        env = os.environ.copy()
        if self.password:
            env['PGPASSWORD'] = self.password

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stderr:
                logger.warning(f"pg_dump warnings: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {e.stderr}")
            raise

    def restore_backup(self, backup_path: Path, confirm: bool = False) -> bool:
        """Restaure une sauvegarde.
        
        Args:
            backup_path: Chemin vers le fichier de sauvegarde
            confirm: Confirmation explicite (défaut: False)
            
        Returns:
            bool: True si la restauration a réussi
        """
        if not confirm:
            logger.warning("⚠️ Restauration non confirmée. Passez confirm=True.")
            return False

        if not backup_path.exists():
            logger.error(f"❌ Fichier de sauvegarde introuvable: {backup_path}")
            return False

        # Vérifier l'intégrité
        if not verify_backup(backup_path):
            logger.error(f"❌ La sauvegarde semble corrompue: {backup_path}")
            return False

        # Vérifier si c'est un fichier compressé
        is_compressed = backup_path.suffix == '.gz'

        if is_compressed:
            cmd = [
                'pg_restore',
                '-h', self.host,
                '-p', self.port,
                '-U', self.user,
                '-d', self.database,
                '--clean',
                '--if-exists',
                str(backup_path),
            ]
        else:
            cmd = [
                'psql',
                '-h', self.host,
                '-p', self.port,
                '-U', self.user,
                '-d', self.database,
                '-f', str(backup_path),
            ]

        env = os.environ.copy()
        if self.password:
            env['PGPASSWORD'] = self.password

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stderr:
                logger.warning(f"Restoration warnings: {result.stderr}")
            logger.info(f"✅ Sauvegarde restaurée: {backup_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erreur lors de la restauration: {e.stderr}")
            return False

    def list_backups(self, limit: int | None = None) -> list[dict]:
        """Liste toutes les sauvegardes disponibles.
        
        Args:
            limit: Nombre maximum de sauvegardes à retourner
            
        Returns:
            list: Liste des sauvegardes
        """
        backups = []
        for file in sorted(self.backup_dir.glob("backup_*"), reverse=True):
            stat = file.stat()
            backups.append({
                'filename': file.name,
                'path': str(file),
                'size': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'is_compressed': file.suffix == '.gz'
            })

        if limit:
            return backups[:limit]
        return backups

    def cleanup_old_backups(self, keep_count: int | None = None) -> int:
        """Supprime les anciennes sauvegardes, en gardant les plus récentes.
        
        Args:
            keep_count: Nombre de sauvegardes à conserver (défaut: config)
            
        Returns:
            int: Nombre de sauvegardes supprimées
        """
        if keep_count is None:
            keep_count = self.keep_count

        backups = sorted(self.backup_dir.glob("backup_*"), reverse=True)

        if len(backups) <= keep_count:
            logger.info(f"Aucune sauvegarde à supprimer (garder {keep_count})")
            return 0

        to_delete = backups[keep_count:]
        deleted = 0

        for file in to_delete:
            try:
                file.unlink()
                deleted += 1
                logger.info(f"🗑️ Sauvegarde supprimée: {file}")
            except Exception as e:
                logger.error(f"❌ Erreur lors de la suppression de {file}: {e}")

        logger.info(f"✅ {deleted} sauvegardes supprimées, {len(backups) - deleted} conservées")
        return deleted

    def get_total_size(self) -> float:
        """Retourne la taille totale des sauvegardes en MB."""
        total = sum(f.stat().st_size for f in self.backup_dir.glob("backup_*"))
        return round(total / (1024 * 1024), 2)


# Instance globale
backup_manager = DatabaseBackup()


async def backup_database() -> dict:
    """Sauvegarde automatique de la base de données."""
    try:
        logger.info("🔄 Démarrage de la sauvegarde automatique...")

        # Créer la sauvegarde
        backup_path = backup_manager.create_backup(compress=True)

        # Nettoyer les anciennes sauvegardes
        deleted = backup_manager.cleanup_old_backups()

        logger.info(f"✅ Sauvegarde automatique terminée: {backup_path}")
        return {
            'success': True,
            'backup_path': str(backup_path),
            'size_mb': round(backup_path.stat().st_size / (1024 * 1024), 2),
            'deleted_count': deleted,
            'total_backups': len(backup_manager.list_backups()),
            'total_size_mb': backup_manager.get_total_size()
        }
    except Exception as e:
        logger.error(f"❌ Erreur lors de la sauvegarde automatique: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


async def scheduled_backup() -> None:
    """Tâche planifiée pour les sauvegardes automatiques."""
    logger.info("📅 Tâche de sauvegarde planifiée démarrée")

    while True:
        try:
            result = await backup_database()
            if result['success']:
                logger.info(f"✅ Sauvegarde planifiée réussie: {result['backup_path']}")
            else:
                logger.error(f"❌ Sauvegarde planifiée échouée: {result['error']}")
        except Exception as e:
            logger.error(f"❌ Erreur dans la tâche planifiée: {e}")

        # Attendre 24 heures
        await asyncio.sleep(24 * 60 * 60)


def export_metadata() -> dict:
    """Exporte les métadonnées des sauvegardes pour le reporting."""
    backups = backup_manager.list_backups()
    return {
        'database': backup_manager.database,
        'backup_dir': str(backup_manager.backup_dir),
        'backups_count': len(backups),
        'backups': backups,
        'total_size_mb': backup_manager.get_total_size(),
        'keep_count': backup_manager.keep_count,
        'compression_enabled': backup_manager.compression,
    }


def verify_backup(backup_path: Path) -> bool:
    """Vérifie l'intégrité d'un fichier de sauvegarde."""
    if not backup_path.exists():
        logger.error(f"❌ Fichier introuvable: {backup_path}")
        return False

    # Vérifier la taille
    if backup_path.stat().st_size == 0:
        logger.error(f"❌ Fichier vide: {backup_path}")
        return False

    # Vérifier l'en-tête pour les fichiers compressés
    if backup_path.suffix == '.gz':
        try:
            with gzip.open(backup_path, 'rb') as f:
                header = f.read(10)
                if not header:
                    logger.error(f"❌ En-tête invalide: {backup_path}")
                    return False
                # Vérifier que c'est un dump PostgreSQL
                if not header.startswith(b'PGDMP'):
                    logger.warning(f"⚠️ Le fichier ne semble pas être un dump PostgreSQL: {backup_path}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification: {e}")
            return False

    return True
