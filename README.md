# TalentIA — Backend (API)

API du SaaS de recrutement **TalentIA ATS** (FastAPI · PostgreSQL · SQLAlchemy).
Architecture multi-tenant, AI-first. Ce dépôt est **séparé** du frontend Next.js.

## Stack

- **FastAPI** (Python 3.12+) — API REST, docs OpenAPI auto (`/docs`)
- **PostgreSQL** via **SQLAlchemy 2.0** + **Alembic** (migrations)
- **Auth** : JWT signé, transporté par un **cookie httpOnly** (jamais de token en localStorage)
- **Poetry** (dépendances) · **Docker Compose** (base de données)

## Démarrage rapide

```bash
# 1. Dépendances
poetry install

# 2. Base de données (PostgreSQL via Docker)
docker compose up -d

# 3. Configuration
cp .env.example .env          # puis générer une vraie SECRET_KEY

# 4. Migrations
poetry run alembic upgrade head

# 5. Lancer l'API (http://localhost:8000, docs sur /docs)
poetry run uvicorn app.main:app --reload
```

## Structure

```
app/
  core/       config, base de données, sécurité (hash + JWT), enums, réponses
  models/     modèles SQLAlchemy (Entreprise, Utilisateur, Abonnement,
              Campagne, Offre, Candidat, Candidature)
  auth/       gestion du cookie de session httpOnly
  api/        dépendances (get_current_user, RBAC) et routes
migrations/   Alembic
```

## Conventions

- **Réponses** : enveloppe `{"success", "message"/"error", "data"}` (voir `app/core/responses.py`).
- **Contrat** : enums (rôles, statuts…) alignés sur le frontend (`lib/types` / `lib/constants`) et le cahier des charges — garder synchronisé des deux côtés.
- **Lots** : ce socle (Lot 0) est commun ; les endpoints métier sont ajoutés lot par lot (auth, entreprises, offres, candidatures, IA, notifications).

## Pour continuer (équipe)

👉 **[docs/GUIDE_BACKEND_EQUIPE.md](docs/GUIDE_BACKEND_EQUIPE.md)** — comment
brancher tes endpoints sur le socle + **ce que chacun a à faire** (Yasmine :
offres/campagnes · Bambara : candidatures/upload CV · Tangara : users/branchement
auth). Recette d'ajout d'endpoint, conventions, coordination des migrations.
