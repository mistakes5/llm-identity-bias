def filter_tasks(self, status=None, priority=None, tag=None, sort_by="id"):
    results = list(self.tasks)

    # TODO: Your implementation here
    # FILTER 1 — Status:   None → "pending" only,  "all" → skip filter
    # FILTER 2 — Priority: exact match when provided
    # FILTER 3 — Tag:      case-insensitive exact match when provided
    # SORT:      "id" asc, "priority" desc (use PRIORITY_ORDER), "created" asc

    return results  # ← replace with filtered & sorted list