tasks/
├── model.py     — Task dataclass + Priority enum
├── storage.py   — Atomic JSON persistence (~/.local/share/tasks/tasks.json)
├── filters.py   — Composable filter predicates ← your contribution here
├── cli.py       — Typer commands + Rich colored table
├── utils.py     — Natural language date parsing
├── __init__.py
└── __main__.py
pyproject.toml