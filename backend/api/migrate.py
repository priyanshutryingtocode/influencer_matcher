from api.repositories.postgres_run_repository import PostgresRunRepository


def main() -> None:
    PostgresRunRepository().ensure_schema()
    print("Run history schema is ready.")


if __name__ == "__main__":
    main()
