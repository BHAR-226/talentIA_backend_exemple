"""Utilitaires d'export de données."""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import StatutCandidature
from app.models.candidature import Candidature
from app.models.offre import Offre

# ==========================================================
# Export CSV
# ==========================================================

def export_candidatures_to_csv(
    candidatures: list[Candidature],
    filename: str = "candidatures_export.csv"
) -> StreamingResponse:
    """Exporte les candidatures au format CSV avec BOM pour Excel.

    Args:
        candidatures: Liste des candidatures à exporter
        filename: Nom du fichier de sortie

    Returns:
        StreamingResponse: Réponse avec le fichier CSV
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    # En-têtes
    headers = [
        'ID', 'Candidat', 'Email', 'Téléphone', 'Offre', 'Statut',
        'Date Soumission', 'Date Analyse', 'Score', 'CV', 'Lettre Motivation',
        'Commentaires', 'Décision', 'Motif Refus'
    ]
    writer.writerow(headers)

    for c in candidatures:
        writer.writerow([
            str(c.id),
            c.candidat.nom if c.candidat else '',
            c.candidat.email if c.candidat else '',
            c.candidat.telephone if c.candidat else '',
            c.offre.titre if c.offre else '',
            c.statut.value if c.statut else '',
            c.date_soumission.strftime('%Y-%m-%d %H:%M') if c.date_soumission else '',
            c.date_analyse.strftime('%Y-%m-%d %H:%M') if c.date_analyse else '',
            c.score_global or '',
            c.cv_url or '',
            _truncate_text(c.lettre_motivation, 100),
            _truncate_text(c.commentaires, 100),
            c.decision_date.strftime('%Y-%m-%d') if c.decision_date else '',
            c.motif_refus or '',
        ])

    output.seek(0)

    # Ajouter BOM pour Excel (UTF-8 avec BOM)
    output_with_bom = io.BytesIO()
    output_with_bom.write('\ufeff'.encode())
    output_with_bom.write(output.getvalue().encode('utf-8'))
    output_with_bom.seek(0)

    return StreamingResponse(
        output_with_bom,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )


# ==========================================================
# Export Excel
# ==========================================================

def export_candidatures_to_excel(
    candidatures: list[Candidature],
    filename: str = "candidatures_export.xlsx"
) -> StreamingResponse:
    """Exporte les candidatures au format Excel (XLSX).

    Args:
        candidatures: Liste des candidatures à exporter
        filename: Nom du fichier de sortie

    Returns:
        StreamingResponse: Réponse avec le fichier Excel
    """
    try:
        from io import BytesIO

        import pandas as pd
        from openpyxl.styles import Alignment, Font, PatternFill

        data = []
        for c in candidatures:
            data.append({
                'ID': str(c.id),
                'Candidat': c.candidat.nom if c.candidat else '',
                'Email': c.candidat.email if c.candidat else '',
                'Téléphone': c.candidat.telephone if c.candidat else '',
                'Offre': c.offre.titre if c.offre else '',
                'Statut': c.statut.value if c.statut else '',
                'Date Soumission': c.date_soumission.strftime('%Y-%m-%d %H:%M') if c.date_soumission else '',
                'Date Analyse': c.date_analyse.strftime('%Y-%m-%d %H:%M') if c.date_analyse else '',
                'Score': c.score_global or '',
                'CV': c.cv_url or '',
                'Lettre Motivation': _truncate_text(c.lettre_motivation, 100),
                'Commentaires': _truncate_text(c.commentaires, 100),
                'Décision': c.decision_date.strftime('%Y-%m-%d') if c.decision_date else '',
                'Motif Refus': c.motif_refus or '',
            })

        df = pd.DataFrame(data)
        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Candidatures', index=False)

            # Style du worksheet
            worksheet = writer.sheets['Candidatures']

            # Style des en-têtes
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")

            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            # Ajuster les largeurs des colonnes
            for column in df.columns:
                col_idx = df.columns.get_loc(column) + 1
                column_letter = chr(64 + col_idx)

                # Calculer la largeur
                max_length = max(
                    df[column].astype(str).map(len).max(),
                    len(column)
                )
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except ImportError as e:
        raise ImportError(
            "pandas ou openpyxl n'est pas installé. "
            "Installez-les avec: pip install pandas openpyxl"
        ) from e


# ==========================================================
# Utilitaires
# ==========================================================

def _truncate_text(text: str | None, max_length: int = 100) -> str:
    """Tronque un texte si nécessaire."""
    if not text:
        return ''
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'


def _format_date(date: datetime | None) -> str:
    """Formate une date pour l'export."""
    if not date:
        return ''
    return date.strftime('%Y-%m-%d %H:%M')


# ==========================================================
# Router FastAPI
# ==========================================================

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/candidatures")
def export_candidatures(
    offre_id: str | None = Query(None, description="Filtrer par ID d'offre"),
    statut: str | None = Query(None, description="Filtrer par statut"),
    date_debut: str | None = Query(None, description="Date de début (YYYY-MM-DD)"),
    date_fin: str | None = Query(None, description="Date de fin (YYYY-MM-DD)"),
    format: str = Query("csv", description="Format d'export: csv ou excel"),
    db: Session = Depends(get_db)
):
    """Exporte les candidatures au format CSV ou Excel.

    **Filtres disponibles :**
    - `offre_id` : Filtrer par offre
    - `statut` : Filtrer par statut
    - `date_debut` : Date de soumission minimum
    - `date_fin` : Date de soumission maximum
    - `format` : csv (défaut) ou excel
    """
    query = db.query(Candidature)

    if offre_id:
        query = query.filter(Candidature.offre_id == offre_id)

    if statut:
        query = query.filter(Candidature.statut == statut)

    if date_debut:
        try:
            date = datetime.strptime(date_debut, '%Y-%m-%d')
            query = query.filter(Candidature.date_soumission >= date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format date_debut invalide. Utilisez YYYY-MM-DD"
            ) from None

    if date_fin:
        try:
            date = datetime.strptime(date_fin, '%Y-%m-%d')
            query = query.filter(Candidature.date_soumission <= date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format date_fin invalide. Utilisez YYYY-MM-DD"
            ) from None

    candidatures = query.order_by(Candidature.date_soumission.desc()).all()

    if not candidatures:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune candidature trouvée avec les critères spécifiés"
        )

    # Générer le nom du fichier
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_base = f"candidatures_{timestamp}"

    if format.lower() == "excel":
        return export_candidatures_to_excel(
            candidatures,
            filename=f"{filename_base}.xlsx"
        )

    return export_candidatures_to_csv(
        candidatures,
        filename=f"{filename_base}.csv"
    )


@router.get("/offres/{offre_id}/candidatures")
def export_candidatures_offre(
    offre_id: str,
    format: str = Query("csv", description="Format d'export: csv ou excel"),
    db: Session = Depends(get_db)
):
    """Exporte les candidatures d'une offre spécifique.
    """
    # Vérifier que l'offre existe
    offre = db.get(Offre, offre_id)
    if not offre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre non trouvée"
        )

    candidatures = offre.candidatures

    if not candidatures:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune candidature pour cette offre"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_base = f"candidatures_{offre.titre.replace(' ', '_')}_{timestamp}"

    if format.lower() == "excel":
        return export_candidatures_to_excel(
            candidatures,
            filename=f"{filename_base}.xlsx"
        )

    return export_candidatures_to_csv(
        candidatures,
        filename=f"{filename_base}.csv"
    )


@router.get("/candidatures/stats")
def export_stats_candidatures(
    db: Session = Depends(get_db)
):
    """Exporte des statistiques sur les candidatures.
    """
    # Statistiques par statut
    stats_par_statut = {}
    for statut in StatutCandidature:
        count = db.query(Candidature).filter(Candidature.statut == statut).count()
        if count > 0:
            stats_par_statut[statut.value] = count

    # Statistiques générales
    total = db.query(Candidature).count()

    stats = {
        "total_candidatures": total,
        "stats_par_statut": stats_par_statut,
        "date_generation": datetime.now().isoformat(),
        "taux_conversion": {
            "pourcentage": round((stats_par_statut.get("embauche", 0) / total * 100), 2) if total > 0 else 0,
            "embauches": stats_par_statut.get("embauche", 0)
        }
    }

    # Retourner en CSV
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow(["Statistiques des Candidatures"])
    writer.writerow([])
    writer.writerow(["Total candidatures", total])
    writer.writerow(["Embauches", stats_par_statut.get("embauche", 0)])
    writer.writerow(["Taux de conversion", f"{stats['taux_conversion']['pourcentage']}%"])
    writer.writerow([])
    writer.writerow(["Statut", "Nombre"])

    for statut, count in stats_par_statut.items():
        writer.writerow([statut, count])

    writer.writerow([])
    writer.writerow(["Date de génération", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=stats_candidatures_{datetime.now().strftime('%Y%m%d')}.csv",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )
