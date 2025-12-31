# To-do Frontend (Tecpap_data-main) vs backend FastAPI

1) Types/DTO à aligner (`src/types/api.ts`)
- `EventType`: remplacer `URGENT_JOB` par `URGENT_ORDER` (nom réel côté backend).
- `HourlyReport`: le backend renvoie `{time, machine:{is_running,is_down,speed_factor,current_format,current_job_id}, queue_size, completed_count, total_lateness_min_est, counters_min:{downtime,stopped,idle,producing}}`. Ajuster l’interface (actuelle: champs plats is_running, is_down, …) et adapter l’usage dans `Reports.tsx`.
- `EngineState.breakdown`: le backend expose `{down_start_time, down_reason, last_breakdown_duration_min, replan_threshold_min}` (actuel: `type, started_at, duration_min`). Mettre le bon shape ou mapper dans `api.ts`.
- `RecomputePlanResponse`: inclure `total_setup_min_est` (et retirer `pid` si inutile) pour refléter `/plan/recompute`.

2) API layer (`src/services/api.ts`)
- (fait) Le front lit désormais la structure native `machine.{is_running,...}` donc pas de mapping nécessaire pour `HourlyReport`.
- (fait) `recomputePlan` force `FORMAT_PRIORITY` pour éviter les 400.
- (fait) Ajout d’un helper `buildUrgentOrderValue` et type `UrgentOrderPayload` pour construire le payload `URGENT_ORDER` (`of_id=...;due=...;format=...;qty=...;nominal_rate=...;duration_min=...;priority=...`).

3) Pages à adapter
- `src/pages/Reports.tsx`: lire les champs dans `report.machine.is_running` / `machine.is_down`, etc., ou consommer les champs mappés si transformés dans `api.ts`. Les séries `queue_size`, `completed_count`, `total_lateness_min_est`, `counters_min.*` restent valides.
- `src/pages/EventsLogs.tsx`: changer la liste déroulante des types pour `URGENT_ORDER`; ajouter un hint sur le format de `value` (chaine `key=value;...`). Le backend ignore les événements en retard >120 min : éventuellement afficher une info/badge.
- `src/pages/Planning.tsx`: retirer/masquer la stratégie `EDD_SETUP` ou la mapper sur `FORMAT_PRIORITY` pour éviter une 400. S’assurer que `due_date` envoyé est en ISO (datetime-local → `toISOString().slice(0,16)` ou équivalent).
- `src/pages/DashboardLive.tsx`: l’état runner/engine est OK, mais si on veut afficher les infos panne, lire `engine.breakdown.down_start_time`, `down_reason`, `last_breakdown_duration_min`. Les boutons “urgent”/panne doivent envoyer des types supportés (`BREAKDOWN_START/END`, `SPEED_CHANGE`, `URGENT_ORDER` si ajouté).

4) Base URL / CORS
- Vérifier `VITE_API_BASE_URL` (par défaut `http://127.0.0.1:8000`) cohérent avec le backend; CORS backend autorise 5173 et 3000.

5) Données OF / Plan
- Le backend renvoie `work_nominal_min` dans `/work-orders`; si absent il peut calculer par défaut. Garder l’affichage mais prévoir `undefined` (fallback “N/A”).
- Export CSV: l’URL `/plan/export.csv?limit=` est déjà correcte; rien à changer.
