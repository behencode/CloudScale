from functools import lru_cache

from app.dynamodb_repo import DynamoRepository
from app.sqlite_repo import SqliteRepository


def build_repository(settings):
    if settings.database_backend == "sqlite":
        repo = SqliteRepository(settings.sqlite_path)
        repo.prepare()
        return repo
    if settings.database_backend == "dynamodb":
        if not settings.dynamodb_table:
            from app.errors import ConfigurationError

            raise ConfigurationError("DYNAMODB_TABLE is required when DATABASE_BACKEND=dynamodb.")
        from app.aws_session import aws_session

        table = aws_session(settings).resource("dynamodb").Table(settings.dynamodb_table)
        return DynamoRepository(table)
    raise RuntimeError(f"Unknown database backend: {settings.database_backend}")


@lru_cache
def repository_method_names() -> tuple[set[str], set[str]]:
    def names(cls):
        return {name for name in dir(cls) if not name.startswith("_")}

    return names(SqliteRepository), names(DynamoRepository)
