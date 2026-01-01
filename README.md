# Tecpap Scheduler Backend

API FastAPI exposant un moteur de planification et de simulation (production, pannes, changements de cadence) alimenté par des données CSV de démonstration.

## Prérequis
- Python 3.11+ recommandé
- `pip install fastapi uvicorn pydantic`

## Démarrage rapide
```bash
python -m venv .venv
. .venv/Scripts/activate  # PowerShell: .venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic
uvicorn api_server:app --reload --port 8000
```
Les données sont chargées depuis `tecpap_synth_data/` (fichiers `work_orders.csv` et `setup_matrix.csv`).

## Données et modèle
- `work_orders.csv` : colonnes attendues `of_id,created_at,due_date,priority,product,format,qty,nominal_rate_u_per_h,nominal_duration_min`. Sert à construire la file d’attente initiale.
- `setup_matrix.csv` : colonnes `from_format,to_format,setup_min` pour les temps de changement de format.
- `machine_history.csv` (nouveau) : colonnes `machine_id,format,trs_percent[,sample_count,avg_setup_min]` pour guider l’assignation multi-machines (fallback TRS=70% si couple manquant). Machines par défaut : 5 et 6.
- Les replans utilisent la matrice de setup ; si aucune méthode de plan n’est fournie par le moteur, un preview est construit depuis la queue en séquence.
- Politique retard d’événements : ignorés si reçus avec >120 min de retard ou si `late_policy="IGNORE"`.
- Replan après panne uniquement si la durée d’arrêt estimée ≥ 30 min (seuil `breakdown_replan_threshold_min`).

## API principale
- `GET /state` : état courant du moteur (temps simulé, format courant, file, KPIs).
- `GET /plan?limit=` : planning prévisionnel (méthode moteur si dispo, sinon preview depuis la queue).
- `GET /plan/export.csv` : export CSV du planning.
- `POST /plan/recompute` : replan multi-machines basé sur TRS (machines 5/6 par défaut), affecte chaque OF à la machine qui termine le plus tôt (setup + TRS) et renvoie l’assignation.
- `GET /machines/history` : historique TRS par machine/format (extrait de `machine_history.csv`).
- `GET /machines/state` : état courant des machines (format courant, disponibilité, flags run/down).
- `GET /work-orders` : liste de la queue (id, format, due_date, priorité, durée nominale).
- `POST /work-orders` : ajoute une OF (persiste dans `work_orders.csv` et pousse dans la queue/pool si présents).
  ```json
  { "of_id": "OF999", "format": "F1", "due_date": "2026-01-05T16:00", "priority": 5, "work_nominal_min": 60 }
  ```
- `POST /setup-matrix` : upsert d’une ligne setup (`from_format,to_format,setup_min`), réécrit le CSV.
- `POST /events` : applique un événement daté `{ "timestamp": "...", "type": "...", "value": "" }`.
- `POST /events/now` : applique un événement à `now` du moteur.
- `GET /events/log` : journal des derniers événements.
- `POST /simulate/day` : simulation “offline” complète d’une journée (retourne rapports horaires, stats, état final).
- Temps réel (simulation compressée) :
  - `POST /realtime/start` : démarre un run compressé `{ "day_start": "...", "day_end": "...", "compress_to_seconds": 600, "tick_seconds": 0.5 }` (envoie automatiquement `SHIFT_START` au démarrage).
  - `POST /realtime/stop`
  - `GET /realtime/state`
  - `GET /realtime/hourly` : rapports horaires accumulés.
- Debug/outil :
  - `GET /debug/engine` : inspecte méthodes/champs liés au planning.
  - `GET /debug/plan-error` : traceback détaillé si /plan échoue.
  - `GET /debug/setup` : lecture rapide d’une valeur de setup.
  - `GET /debug/queue` : taille et premiers ids de queue.
  - `GET /debug/pid` : PID du process.
- CORS autorisé pour `http://localhost:5173`, `127.0.0.1:5173`, `localhost:3000`, `127.0.0.1:3000`.

## Événements supportés (champ `type`)
- `SHIFT_START`, `SHIFT_STOP`
- `SPEED_CHANGE` (`value` = facteur > 0)
- `URGENT_ORDER` (`value` = chaîne `of_id=...;due=...;format=...;qty=...;nominal_rate=...;duration_min=...;priority=...`)
- `BREAKDOWN_START`, `BREAKDOWN_END` (replan si arrêt ≥ 30 min)
Les événements en avance font avancer l’horloge ; les événements en retard >120 min sont ignorés par défaut.

## Exemples rapides
- Envoyer une panne immédiate :  
  ```json
  POST /events/now
  { "type": "BREAKDOWN_START", "value": "maintenance" }
  ```
- Ajouter une urgente :  
  ```json
  POST /events/now
  { "type": "URGENT_ORDER", "value": "of_id=URG123;due=2026-01-05T12:00;format=F2;qty=800;nominal_rate=400;duration_min=90;priority=10" }
  ```
- Replan à partir du format courant :  
  ```json
  POST /plan/recompute
  { "strategy": "FORMAT_PRIORITY" }
  ```
- Démarrer le mode temps réel compressé :  
  ```json
  POST /realtime/start
  { "day_start": "2026-01-05T08:00", "day_end": "2026-01-05T20:00", "compress_to_seconds": 600, "tick_seconds": 0.5 }
  ```
