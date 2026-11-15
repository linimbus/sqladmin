from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from ..config import MAX_ROWS_LIMIT
from ..models import Connection
from .connections import apply_schema, get_engine, sanitize_error
from .serialize import serialize_value

READ_ONLY_PREFIXES = {
    "select",
    "with",
    "show",
    "explain",
    "describe",
    "desc",
    "pragma",
    "values",
    "table",
}


class ReadOnlyViolation(Exception):
    pass


def strip_leading_comments(sql: str) -> str:
    text = sql.lstrip("\ufeff \t\r\n")
    while True:
        if text.startswith("--") or text.startswith("#"):
            index = text.find("\n")
            if index == -1:
                return ""
            text = text[index + 1 :].lstrip()
        elif text.startswith("/*"):
            index = text.find("*/")
            if index == -1:
                return ""
            text = text[index + 2 :].lstrip()
        else:
            return text


def statement_keyword(sql: str) -> str:
    cleaned = strip_leading_comments(sql)
    match = re.match(r"([A-Za-z]+)", cleaned)
    return match.group(1).upper() if match else "UNKNOWN"


def is_read_only_statement(sql: str) -> bool:
    keyword = statement_keyword(sql).lower()
    if keyword not in READ_ONLY_PREFIXES:
        return False
    if keyword == "with":
        body = strip_leading_comments(sql)
        if re.search(
            r"\b(insert|update|delete|merge|create|drop|alter|truncate|grant|revoke|call|exec|execute)\b",
            body,
            re.IGNORECASE,
        ):
            return False
    return True


def split_sql(sql: str) -> List[str]:
    """Split a SQL script into statements, respecting quotes and comments."""
    statements: List[str] = []
    buffer: List[str] = []
    i = 0
    length = len(sql)

    while i < length:
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < length else ""

        if char == "-" and next_char == "-":
            end = sql.find("\n", i)
            if end == -1:
                buffer.append(sql[i:])
                break
            buffer.append(sql[i : end + 1])
            i = end + 1
            continue

        if char == "#":
            line_start = sql.rfind("\n", 0, i) + 1
            if sql[line_start:i].strip() == "":
                end = sql.find("\n", i)
                if end == -1:
                    buffer.append(sql[i:])
                    break
                buffer.append(sql[i : end + 1])
                i = end + 1
                continue

        if char == "/" and next_char == "*":
            end = sql.find("*/", i + 2)
            if end == -1:
                buffer.append(sql[i:])
                break
            buffer.append(sql[i : end + 2])
            i = end + 2
            continue

        if char in ("'", '"', "`"):
            quote = char
            j = i + 1
            buffer.append(char)
            while j < length:
                current = sql[j]
                buffer.append(current)
                if current == "\\" and quote in ("'", '"') and j + 1 < length:
                    buffer.append(sql[j + 1])
                    j += 2
                    continue
                if current == quote:
                    if j + 1 < length and sql[j + 1] == quote:
                        buffer.append(sql[j + 1])
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            i = j
            continue

        if char == "$":
            match = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
            if match:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                if end != -1:
                    end += len(tag)
                    buffer.append(sql[i:end])
                    i = end
                    continue

        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            i += 1
            continue

        buffer.append(char)
        i += 1

    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)
    return [item for item in statements if strip_leading_comments(item).strip()]


def _enable_database_read_only(connection, kind: str) -> None:
    statements = {
        "sqlite": "PRAGMA query_only = ON",
        "postgresql": "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY",
        "mysql": "SET SESSION TRANSACTION READ ONLY",
    }
    statement = statements.get(kind)
    if statement:
        try:
            connection.exec_driver_sql(statement)
        except Exception:
            pass


def execute_sql(
    conn: Connection,
    sql: str,
    max_rows: int = 500,
    database: Optional[str] = None,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    statements = split_sql(sql)
    if not statements:
        raise ValueError("请输入要执行的 SQL 语句")

    if conn.read_only:
        blocked = [statement for statement in statements if not is_read_only_statement(statement)]
        if blocked:
            raise ReadOnlyViolation(
                "当前连接处于只读模式，只能执行 SELECT / SHOW / EXPLAIN / DESCRIBE / PRAGMA 等查询语句"
            )

    max_rows = max(1, min(int(max_rows), MAX_ROWS_LIMIT))
    engine = get_engine(conn, database)
    results: List[Dict[str, Any]] = []
    overall_error: Optional[str] = None
    overall_started = time.perf_counter()

    with engine.connect() as connection:
        if conn.read_only:
            _enable_database_read_only(connection, conn.kind)
        try:
            apply_schema(connection, conn.kind, schema)
        except Exception:
            pass

        for index, statement in enumerate(statements, start=1):
            started = time.perf_counter()
            statement_type = statement_keyword(statement)
            try:
                result = connection.exec_driver_sql(statement)
                elapsed = round((time.perf_counter() - started) * 1000, 1)
                if result.returns_rows:
                    fetched = result.fetchmany(max_rows + 1)
                    truncated = len(fetched) > max_rows
                    rows = [
                        [serialize_value(value) for value in row]
                        for row in fetched[:max_rows]
                    ]
                    columns = [{"name": str(key), "type": "", "nullable": True} for key in result.keys()]
                    results.append(
                        {
                            "index": index,
                            "statement": statement,
                            "type": statement_type,
                            "columns": columns,
                            "rows": rows,
                            "row_count": len(rows),
                            "truncated": truncated,
                            "duration_ms": elapsed,
                            "error": None,
                        }
                    )
                else:
                    row_count = result.rowcount
                    if row_count is not None and row_count < 0:
                        row_count = None
                    results.append(
                        {
                            "index": index,
                            "statement": statement,
                            "type": statement_type,
                            "columns": [],
                            "rows": [],
                            "row_count": row_count,
                            "truncated": False,
                            "duration_ms": elapsed,
                            "error": None,
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                elapsed = round((time.perf_counter() - started) * 1000, 1)
                message = sanitize_error(exc)
                results.append(
                    {
                        "index": index,
                        "statement": statement,
                        "type": statement_type,
                        "columns": [],
                        "rows": [],
                        "row_count": None,
                        "truncated": False,
                        "duration_ms": elapsed,
                        "error": message,
                    }
                )
                overall_error = message
                try:
                    connection.rollback()
                except Exception:
                    pass
                break

        if conn.read_only:
            try:
                connection.rollback()
            except Exception:
                pass
        elif overall_error is None:
            try:
                connection.commit()
            except Exception as exc:  # noqa: BLE001
                overall_error = sanitize_error(exc)

    return {
        "ok": overall_error is None,
        "results": results,
        "duration_ms": round((time.perf_counter() - overall_started) * 1000, 1),
        "error": overall_error,
        "read_only": bool(conn.read_only),
    }
