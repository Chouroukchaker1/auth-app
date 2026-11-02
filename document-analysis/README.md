# Analyse de document

Lit un document papier (photo, scan ou PDF) avec le modèle **Nanonets-OCR2-3B**, 100 % en local,
puis remplit le formulaire adhérent de l'application.

```
Angular /member/analyse ──► Spring Boot /api/analyses (login JWT) ──► api.py (ce dossier, port 8501)
```

L'interface est la page Angular **تحليل وثيقة / Analyse de document**, ouverte depuis le formulaire
adhérent : charger le document, suivre l'avancement, corriger les valeurs (orange = à vérifier),
puis **ملء الاستمارة / Remplir le formulaire**. Rien n'est enregistré avant **حفظ** dans le formulaire.

## Fichiers

| Fichier | Rôle |
|---|---|
| `api.py` | Service HTTP : file d'analyses (une à la fois), avancement, résultat |
| `document.py` | Ouverture des images et des PDF (toutes les pages) |
| `ocr_engine.py` | Chargement du modèle, lecture d'une image, score de confiance |
| `form_layout.py` | Redressement de la photo, détection du tableau et des cases (OpenCV) |
| `form_reader.py` | Lecture structurée : champs du haut + tableau, post-traitement |
| `form_link.py` | Conversion vers les champs du formulaire adhérent (libellés arabes ou français) |
| `export.py` | Résultat en JSON, Excel, PDF |
| `scan_document.py` | Même analyse en ligne de commande (fichiers Excel / PDF / JSON) |
| `test_analysis.py` | Tests rapides sans le modèle (lancés par Jenkins) |
| `exemples/` | Formulaires pour tester |

## Lancer sur le PC (carte graphique NVIDIA, le plus rapide)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
python api.py                      # http://localhost:8501
```

Le backend Docker joint alors le service avec `OCR_SERVICE_URL=http://host.docker.internal:8501`
(fichier `.env` à la racine).

## Lancer avec Docker

```powershell
docker compose --profile analyse up -d                                                  # CPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile analyse up -d  # NVIDIA
```

Le modèle (~7,5 Go) est téléchargé au premier démarrage dans le volume `analysis_models`.

## Autres documents

- **Formats** : PNG, JPG, TIFF (plusieurs pages), PDF (jusqu'à 10 pages).
- **Lecture** : tout le texte est lu ; les lignes « libellé : valeur » deviennent des champs, et un tableau
  quadrillé est lu case par case.
- **Remplissage du formulaire** : les libellés sont reconnus en arabe ou en français, même mal lus
  (« Nom et prénom », « الاسم واللقب », « Date de naissance »…), ainsi que les dates en lettres
  (« 10 octobre 1980 ») et les chiffres arabes. Un champ non reconnu reste visible dans les résultats
  et se corrige à la main.

## Ligne de commande et options

```powershell
python scan_document.py exemples\document.png          # une image
python scan_document.py "C:\mes_scans" --debug          # un dossier + image de la grille
python test_analysis.py                                  # tests sans le modèle
```

- `OCR_HOST` / `OCR_PORT` : adresse d'écoute du service (défaut `127.0.0.1:8501`).
- `OCR_QUANTIZE` : `4bit` ou `8bit` pour forcer la compression du modèle sur GPU.
- `OCR_API_URL` : envoi du JSON à une autre API (`scan_document.py --api`).
- `OCR_ADAPTER` : complément LoRA à charger (optionnel, nécessite `pip install peft`).
  Les compléments déjà appris (`forms`, `khatt`, archivés) ont été mesurés le 29/10/2026 sur les
  3 formulaires de référence : moins de valeurs exactes (45 et 46/77 contre 53/77), plus d'erreurs
  affichées sûres et 3 fois plus lents. Essayé aussi le 30/10/2026 en « expert » limité aux noms
  manuscrits (lecture de plus, gardée si plus sûre) : 50/77 et 3 fois plus lent, des lectures fausses
  se déclarant sûres. Ils ne sont donc pas utilisés.
