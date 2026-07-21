# Standard logowania

Logi powinny być strukturalne i zapisywane w JSON Lines.

Wspólne pola:
- `timestamp`
- `level`
- `event`
- `project_id`
- `run_id`
- `module`
- `message`
- `details`

Ważne zdarzenia:
- `search_started`
- `search_completed`
- `raw_saved`
- `normalization_completed`
- `deduplication_completed`
- `export_completed`
- `manual_decision_recorded`
- `error`

Log nie może zawierać kluczy API ani innych sekretów.
