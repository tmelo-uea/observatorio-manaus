#!/usr/bin/env python3
"""Backup lógico do banco em SQL puro, escrito no stdout.

Usa apenas pymysql (já é dependência) e a mesma configuração de conexão do
resto do projeto (DATABASE_URL / MYSQL_URL / MYSQL_*). Não precisa do cliente
`mysqldump` instalado — por isso funciona DENTRO do contêiner do Railway, que
alcança o banco interno (mysql.railway.internal).

Uso típico (de fora, sem expor o banco publicamente):

    railway ssh --service coletor -- python scripts/backup_db.py \
        | gzip > backups/observatorio_$(date +%Y%m%d_%H%M%S).sql.gz

O arquivo gerado é restaurável com:

    gunzip < backup.sql.gz | mysql -h HOST -P PORT -u USER -p NOME_DO_BANCO
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_engine

BATCH = 200


def _dump() -> None:
    engine = get_engine()
    raw = engine.raw_connection()
    conn = raw.driver_connection  # pymysql.Connection (tem .escape)
    out = sys.stdout
    try:
        cur = raw.cursor()
        cur.execute("SHOW TABLES")
        tables = [r[0] for r in cur.fetchall()]

        out.write("-- Observatório de Manaus — backup lógico\n")
        out.write("SET NAMES utf8mb4;\n")
        out.write("SET FOREIGN_KEY_CHECKS=0;\n")

        for t in tables:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            create_sql = cur.fetchone()[1]
            out.write(f"\n-- Tabela: {t}\n")
            out.write(f"DROP TABLE IF EXISTS `{t}`;\n")
            out.write(create_sql + ";\n")

            cur.execute(f"SELECT * FROM `{t}`")
            cols = [d[0] for d in cur.description]
            collist = ",".join(f"`{c}`" for c in cols)

            rows = cur.fetchmany(BATCH)
            while rows:
                values = []
                for row in rows:
                    vals = ",".join(
                        "NULL" if v is None else conn.escape(v) for v in row
                    )
                    values.append(f"({vals})")
                out.write(
                    f"INSERT INTO `{t}` ({collist}) VALUES "
                    + ",".join(values)
                    + ";\n"
                )
                rows = cur.fetchmany(BATCH)

        out.write("\nSET FOREIGN_KEY_CHECKS=1;\n")
        out.flush()
        sys.stderr.write(f"OK — {len(tables)} tabelas exportadas.\n")
    finally:
        raw.close()


if __name__ == "__main__":
    _dump()
