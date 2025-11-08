# scripts/db_apply.py
import os
import argparse
from pathlib import Path
from sqlalchemy import create_engine, text

def load_sql_statements(path: Path):
    raw = path.read_text(encoding="utf-8")
    # remove linhas de meta-comandos do psql (p.ex.: \c dbname)
    lines = []
    for ln in raw.splitlines():
        if ln.strip().startswith("\\"):  # ignora \c, \connect, etc.
            continue
        lines.append(ln)
    sql = "\n".join(lines)
    # separa por ';' simples (OK para seus arquivos, que não têm plpgsql)
    stmts = [s.strip() for s in sql.split(";") if s.strip()]
    return stmts

def run_sql(engine, stmts):
    with engine.begin() as conn:
        for s in stmts:
            conn.exec_driver_sql(s)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", action="store_true", help="Aplica o schema_postgres.sql")
    parser.add_argument("--seed", action="store_true", help="Aplica o seed_postgres.sql")
    parser.add_argument("--all", action="store_true", help="Aplica schema e seed")
    parser.add_argument("--reset", action="store_true",
                        help="Antes do seed: TRUNCATE RESTART IDENTITY CASCADE nas tabelas centrais")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL não definido.")

    engine = create_engine(db_url, future=True)

    base = Path(__file__).resolve().parent.parent / "db"
    schema_file = base / "create.txt"
    seed_file   = base / "populate.txt"

    if args.all or args.schema:
        print(f"==> Schema: {schema_file}")
        run_sql(engine, load_sql_statements(schema_file))
        print("OK schema")

    if args.all or args.seed:
        if args.reset:
            print("==> Resetando tabelas (TRUNCATE … RESTART IDENTITY CASCADE)")
            reset_sql = """
            DO $$
            DECLARE r RECORD;
            BEGIN
              FOR r IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
              LOOP
                EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
              END LOOP;
            END$$;
            """
            run_sql(engine, [reset_sql])
        print(f"==> Seed: {seed_file}")
        run_sql(engine, load_sql_statements(seed_file))
        print("OK seed")

if __name__ == "__main__":
    main()
