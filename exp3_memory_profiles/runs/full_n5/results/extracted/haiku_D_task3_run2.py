task/
  errors.py   — ValidationError, NotFoundError, StorageError hierarchy
  model.py    — Task dataclass + validation (structural no-error-as-data enforcement)
  db.py       — schema init (WAL mode), CRUD, SQL queries
  filters.py  — composable SQL WHERE builder ← you'll fill in one function
  output.py   — table formatter
  cli.py      — argparse subcommands + exception boundary (exit codes 1/2/130)
pyproject.toml  — entry point: task