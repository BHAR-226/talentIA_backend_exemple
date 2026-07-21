# Guide backend — pour continuer sur le socle

Ce guide explique **comment brancher tes endpoints sur le socle** (livré par
Azaël) et **ce que chacun a à faire**. Objectif : que personne ne réinvente
l'auth, la session DB ou les conventions — tout est déjà là.

---

## 1. Ce que le socle te donne (à réutiliser, ne pas recréer)

| Besoin | Où | Comment l'utiliser |
| --- | --- | --- |
| Session DB | `app.core.database.get_db` | `db: Session = Depends(get_db)` |
| Utilisateur connecté | `app.api.deps.get_current_user` | `user: Utilisateur = Depends(get_current_user)` (refuse les candidats) |
| Session candidat **ou** interne | `app.api.deps.get_current_identity` | pour les routes accessibles aux candidats |
| Contrôle par rôle (RBAC) | `app.api.deps.require_roles(...)` | `Depends(require_roles(RoleUtilisateur.admin_rh))` |
| Réponse standard | `app.core.responses.success(...)` | `return success(data, "message")` |
| Enums (rôles, statuts…) | `app.core.enums` | alignés frontend + CDC, **ne pas dupliquer** |
| Modèles de base | `app.models.*` | **squelettes déjà créés** — tu les **complètes** |

**Auth déjà livrée** : `POST /auth/register`, `/auth/login`, `/auth/logout`,
`GET /auth/me` (JWT en cookie httpOnly). Rien à refaire côté auth.

---

## 2. Recette pour ajouter un endpoint (4 étapes)

1. **Modèle** (`app/models/xxx.py`) : compléter le squelette avec tes champs.
2. **Schéma** (`app/schemas/xxx.py`) : `XxxCreate`, `XxxUpdate`, `XxxResponse`
   (Pydantic ; `model_config = ConfigDict(from_attributes=True)` pour lire un ORM).
3. **Route** (`app/api/routes/xxx.py`) : `router = APIRouter(prefix="/xxx", tags=["xxx"])`,
   endpoints avec `Depends(get_current_user)` + `success(...)`.
4. **Brancher** dans `app/main.py` : `app.include_router(xxx.router)`.
5. **Migration** : `poetry run alembic revision --autogenerate -m "xxx"` puis
   `poetry run alembic upgrade head`.

> ⚠️ **Multi-tenant** : filtre TOUJOURS par entreprise. Une offre/candidature
> se rattache à une entreprise via `campagne.entreprise_id`. Ne jamais renvoyer
> les données d'un autre tenant (sauf `admin_plateforme`).

---

## 3. Conventions (obligatoires)

- **Réponses** : toujours via `success(data, message)` → `{success, message, data}`.
  Les erreurs passent par `HTTPException` (déjà formatées par le socle).
- **snake_case** partout (aligné frontend + futur JSON API).
- **Sécurité** : jamais renvoyer de token/hash dans une réponse. La session vit
  dans le cookie httpOnly, point.
- **Rôles** : `recruteur`, `admin_rh`, `admin_plateforme`, `evaluateur_technique`
  (+ `Candidat` = entité séparée). Voir `RoleUtilisateur`.

---

## 4. Ta partie, personne par personne

### 👩‍💼 Yasmine — Offres & Campagnes

**Modèles à compléter** (squelettes existants) :
- `app/models/campagne.py` — a déjà : `intitule, departement, date_limite, nombre_postes`.
  **À ajouter** (CDC §6) : `localisation, competences, experience, langues,
  niveau_etudes, type_contrat, salaire, recruteurs_responsables, workflow`.
- `app/models/offre.py` — a déjà : `titre, description, type_contrat,
  localisation, salaire_min/max, statut, date_publication, reception_ouverte,
  champs_personnalises_def`. **À compléter** si besoin (missions, soft skills…).

**Endpoints à créer** (`app/api/routes/campagnes.py`, `offres.py`) :
- `POST/GET/PUT /campagnes` (scopés `entreprise_id` du user).
- `POST/GET/PUT/DELETE /offres` — statuts brouillon/publiee/archivee.
- **Bouton « Arrêter »** (#1) : `PUT /offres/{id}/reception` → bascule
  `reception_ouverte` (le champ existe déjà !).
- Filtre/recherche offres (statut, mots-clés).
- (S5) `GET /dashboard/stats` recruteur.

**RBAC** : `recruteur` et `admin_rh` de l'entreprise propriétaire.

---

### 🧑‍💻 Bambara — Candidatures & Upload CV

**Modèle à compléter** : `app/models/candidature.py` — a déjà : `statut,
date_soumission, lettre_motivation, cv_url, champs_personnalises, score_global,
evaluation_ia`. **À ajouter** au besoin (CDC §8) : `portfolio, certifications,
diplomes, references`.

**Endpoints à créer** (`app/api/routes/candidatures.py`) :
- `POST /candidatures` **avec upload CV réel** : `fichier: UploadFile = File(...)`
  (`python-multipart` déjà installé). **Valider** format (PDF/DOCX) + taille max ;
  stockage local ou S3-compatible → renseigne `cv_url`.
- **Vérifier `offre.reception_ouverte`** avant d'accepter (sinon 409).
- **Champs perso** (#4) : valider les réponses reçues contre
  `offre.champs_personnalises_def`, stocker dans `candidature.champs_personnalises`.
- `PUT /candidatures/{id}/statut` — changement de statut (branche le Kanban).
- Profil candidat + historique de ses candidatures.

**Accès candidat** : utilise `get_current_identity` (type `candidat`), pas
`get_current_user`.

---

### 👩‍🔧 Tangara — Utilisateurs & branchements Auth/Admin

**Auth = déjà livrée par Azaël** → tu **branches le frontend** dessus :
- `lib/auth/actions.ts` (Next) appelle `POST /auth/register`, `/auth/login`,
  `/auth/logout`, `GET /auth/me` avec **`credentials: "include"`** (cookie).
- Ta logique « nouvelle entreprise → admin_rh / existante → recruteur » est déjà
  implémentée côté backend dans `register`.

**Modèle** : `app/models/utilisateur.py` **existe déjà** (`nom, email,
mot_de_passe_hash, role, actif`) — **ne pas le recréer**, l'étendre si besoin.

**Endpoints à créer** (`app/api/routes/users.py`) :
- `POST/GET/PUT /users` — créer, lister, éditer, **désactiver** (via `actif`),
  scopés `entreprise_id`, RBAC `admin_rh`.
- Gestion des rôles à l'écran (attribution recruteur/admin).
- Admin plateforme : les endpoints `entreprises` existent déjà (liste/lecture/
  édition) — compléter la **suspension** d'entreprise si besoin.

---

## 5. Migrations Alembic — coordination (important)

Plusieurs personnes modifient les modèles → risque de conflit de migrations.
Règles :
- Une migration par feature, message clair (`-m "offres: champs campagne"`).
- **Toujours** `git pull` + `alembic upgrade head` **avant** de générer la tienne.
- Ne jamais éditer une migration déjà poussée ; en créer une nouvelle.
- Vérifier la migration générée avant de l'appliquer (autogenerate n'est pas parfait).

---

## 6. Checklist avant ta PR

```bash
poetry run ruff check app          # lint
poetry run python -c "from app.main import app"   # l'app importe
poetry run alembic upgrade head    # migrations OK
```

CI (GitHub Actions) rejoue ruff + import à chaque PR : garde-la verte.
