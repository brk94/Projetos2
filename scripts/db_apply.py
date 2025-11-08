# scripts/db_apply.py
import os
import argparse
import re
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError

def strip_sql_comments(sql: str) -> str:
    # remove linhas que começam com meta-comandos do psql (\c, \connect, etc.)
    sql = "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("\\"))
    # remove comentários de bloco /* ... */
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    # remove comentários de linha -- ... (apenas do -- até o fim da linha)
    sql = re.sub(r"(?m)--.*?$", "", sql)
    return sql

def load_sql_statements(path: Path):
    raw = path.read_text(encoding="utf-8")
    cleaned = strip_sql_comments(raw).strip()
    # separa por ';' e elimina vazios
    stmts = [s.strip() for s in cleaned.split(";") if s.strip()]
    return stmts

def run_sql(engine, stmts, ignore_exists=False):
    with engine.begin() as conn:
        for s in stmts:
            try:
                conn.exec_driver_sql(s)
            except ProgrammingError as e:
                msg = str(e).lower()
                if ignore_exists and (
                    "already exists" in msg or
                    "duplicate table" in msg or
                    "duplicate object" in msg or
                    "relation" in msg and "already exists" in msg
                ):
                    # segue adiante se já existir
                    continue
                # ignora queries vazias por precaução
                if "can't execute an empty query" in msg:
                    continue
                raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--reset", action="store_true",
                        help="TRUNCATE RESTART IDENTITY CASCADE antes do seed")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL não definido.")

    engine = create_engine(db_url, future=True)

    base = Path(__file__).resolve().parent.parent / "db"
    schema_file = base / "create.txt"     # confirme os nomes
    seed_file   = base / "populate.txt"

    # Só aplica schema se --schema OU --all
    if args.all or args.schema:
        print(f"==> Schema: {schema_file}")
        run_sql(engine, load_sql_statements(schema_file), ignore_exists=True)
        print("OK schema")

    # Só aplica seed se --seed OU --all
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