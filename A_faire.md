# To-do multi-machines (backend + frontend)

## Backend (FastAPI) — FAIT
- Moteur multi-machines (machines 5 et 6 par défaut) avec TRS par format (`machine_history.csv`), assignation au meilleur TRS/fin la plus tôt, recalcul lateness.
- `/plan` + export incluent `machine_id` et `due_date`; `/plan/recompute` utilise la stratégie `MULTI_MACHINE_TRS` et retourne les assignations.
- Endpoints machines : `GET /machines/history` (lecture `machine_history.csv`), `GET /machines/state`.
- README mis à jour (CSV TRS, règle d’assignation, replan multi-machines).

## Frontend (Tecpap_data-main)
- Types (`src/types/api.ts`) : ajouter `machine_id?: string` à `PlanItem`; ajouter `MachineHistory` (machine_id, format, trs_percent, sample_count?, avg_setup_min?); type `MachineState` si endpoint exposé.
- Services (`src/services/api.ts`) : propager `machine_id` dans `getPlan`; ajouter `getMachineHistory()` (et `getMachinesState()` si dispo).
- Planning (`src/pages/Planning.tsx`) : afficher une colonne “Machine” dans le tableau de planification et dans l’export/CSV; optionnel filtre par machine.
- Nouvelle page `src/pages/MachinesHistory.tsx` : tableau des TRS par machine/format, résumés par machine (TRS moyen, meilleur/pire format), filtres machine/format, style cohérent (Card/Badge/Button).
- `src/App.tsx` : ajouter un onglet/menu “Machines” pointant vers la page MachinesHistory.

## Vérifs manuelles
- Créer OF F1/F2 avec TRS M5>M6 sur F1 et M6>M5 sur F2, vérifier `/plan` assigne la meilleure machine et ajuste les durées.
- Envoyer un `URGENT_ORDER` et vérifier le réordonnancement/affectation multi-machines.
