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
- (fait) `Reports.tsx` lit `report.machine.is_running/is_down`.
- (fait) `EventsLogs.tsx` dropdown sur `URGENT_ORDER` + hint sur le format de value.
- (fait) `Planning.tsx` verrouille la stratégie sur `FORMAT_PRIORITY` (dropdown désactivé).
- (fait) `Planning.tsx`: conversion due_date -> ISO avant POST.
- (fait) `DashboardLive.tsx`: affiche breakdown et bouton de test URGENT_ORDER.

4) Base URL / CORS
- Vérifier `VITE_API_BASE_URL` (par défaut `http://127.0.0.1:8000`) cohérent avec le backend; CORS backend autorise 5173 et 3000.

5) Données OF / Plan
- Le backend renvoie `work_nominal_min` dans `/work-orders`; si absent il peut calculer par défaut. Garder l’affichage mais prévoir `undefined` (fallback “N/A”).
- Export CSV: l’URL `/plan/export.csv?limit=` est déjà correcte; rien à changer.
