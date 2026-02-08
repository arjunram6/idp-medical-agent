"""
Genie text-to-SQL: Convert plain English questions into SQL and run against Ghana facility data.
Uses DuckDB locally; swap execution layer for Databricks if needed.
"""

from pathlib import Path


def _get_csv_path() -> Path | None:
    from src.config import _find_ghana_csv
    p = _find_ghana_csv()
    return Path(p) if p else None


def _get_schema_description() -> str:
    """Build a short schema description for the LLM (column names + types from CSV)."""
    path = _get_csv_path()
    if not path or not path.exists():
        return "Table 'facilities' with columns: name TEXT, description TEXT, address_city TEXT, address_stateOrRegion TEXT, capability TEXT, procedure TEXT, equipment TEXT, organization_type TEXT, facilityTypeId TEXT."
    try:
        import duckdb
        conn = duckdb.connect(":memory:")
        conn.execute(f"CREATE TABLE facilities AS SELECT * FROM read_csv_auto({str(path)!r}, header=true)")
        desc = conn.execute("DESCRIBE facilities").fetchall()
        conn.close()
        parts = [f"{row[0]} ({row[1]})" for row in desc]
        return "Table 'facilities' with columns: " + ", ".join(parts[:30]) + (" ..." if len(parts) > 30 else "")
    except Exception:
        return "Table 'facilities' with columns: name, description, capability, procedure, equipment, address_city, address_stateOrRegion, organization_type, facilityTypeId (all TEXT)."


def _generate_sql(question: str, schema_desc: str) -> str | None:
    """Use LLM to generate DuckDB-compatible SQL for the given question."""
    try:
        from openai import OpenAI
        from src.config import OPENAI_API_KEY, LLM_MODEL
        if not OPENAI_API_KEY:
            return None
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""You are a SQL expert. Given this schema:
{schema_desc}

Generate a single DuckDB SQL query that answers this question. Return only the SQL, no explanation. Use table name 'facilities'. Use read_csv_auto if the table is not yet loaded.
Question: {question}"""
        r = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        sql = (r.choices[0].message.content or "").strip()
        if sql.startswith("```"):
            lines = sql.split("\n")
            out = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    out.append(line)
            sql = "\n".join(out) if out else sql
        return sql if "SELECT" in sql.upper() else None
    except Exception:
        return None


def run_text_to_sql(question: str, csv_path: Path | None = None) -> str:
    """
    Convert question to SQL and run it. Uses DuckDB; for Databricks, replace the execution block.
    Returns a human-readable answer string.
    """
    path = csv_path or _get_csv_path()
    if not path or not path.exists():
        return "No Ghana facility CSV found. Add the CSV to data/ or Desktop to use text-to-SQL."

    try:
        import duckdb
    except ImportError:
        return "DuckDB is not installed. Install with: pip install duckdb"

    schema_desc = _get_schema_description()
    sql = _generate_sql(question, schema_desc)
    if not sql:
        return "Could not generate a SQL query for that question. Try rephrasing or use the regular Genie chat."

    # Run on DuckDB (swap for Databricks/sqlalchemy here if needed)
    try:
        conn = duckdb.connect(":memory:")
        conn.execute(f"CREATE TABLE facilities AS SELECT * FROM read_csv_auto({str(path)!r}, header=true)")
        cur = conn.execute(sql)
        result = cur.fetchall()
        col_names = [d[0] for d in cur.description] if cur.description else [f"col_{i}" for i in range(len(result[0]) if result else 0)]
        conn.close()
    except Exception as e:
        return f"SQL execution failed: {e}\nGenerated SQL: {sql}"

    if not result:
        return "The query returned no rows."
    # Format as readable text
    lines = []
    if col_names:
        lines.append(" | ".join(str(c) for c in col_names))
        lines.append("-" * 50)
    for row in result[:50]:
        lines.append(" | ".join(str(v) for v in row))
    if len(result) > 50:
        lines.append(f"... and {len(result) - 50} more rows.")
    return "\n".join(lines)
