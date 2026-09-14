def statement_rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)
