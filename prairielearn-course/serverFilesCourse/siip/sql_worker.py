"""Execute SQL as data in a fresh bounded process; no third-party extensions."""
import json
import os
import re
import sqlite3
import sys
import time


def execute(payload):
    sql = payload['sql']
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 12000:
        return {'status': 'unsupported_query', 'error': 'Empty or oversized SQL.'}
    # This is only an initial scope check. SQLite's parser and authorizer enforce safety.
    head = re.sub(r'/\*.*?\*/|--[^\n]*', ' ', sql, flags=re.S).lstrip().split(None, 1)
    if not head or head[0].upper() not in {'SELECT', 'WITH'}:
        return {'status': 'unsupported_query', 'error': 'Only one read-only SELECT is supported.'}
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        if sys.platform != 'darwin':
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
    except (ImportError, ValueError, OSError):
        pass  # SQLite limits and parent deadline apply on every supported host.
    con = sqlite3.connect(':memory:')
    con.executescript(payload['schema'])
    con.execute('PRAGMA query_only=ON')
    if hasattr(con, "enable_load_extension"):
        con.enable_load_extension(False)
    for category, value in [(sqlite3.SQLITE_LIMIT_LENGTH, 100000),
                            (sqlite3.SQLITE_LIMIT_SQL_LENGTH, 12000),
                            (sqlite3.SQLITE_LIMIT_COLUMN, 32),
                            (sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 60),
                            (sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 12),
                            (sqlite3.SQLITE_LIMIT_VDBE_OP, 40000)]:
        con.setlimit(category, value)
    safe_functions = {'count', 'min', 'max', 'sum', 'avg', 'total', 'coalesce', 'ifnull',
                      'nullif', 'lower', 'upper', 'length', 'substr', 'substring', 'trim',
                      'ltrim', 'rtrim', 'abs', 'round', 'typeof', 'like', 'glob'}
    def authorize(action, arg1, arg2, db, trigger):
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if arg1.lower() in {'employees', 'departments'} else sqlite3.SQLITE_DENY
        if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE}:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() in safe_functions:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    con.set_authorizer(authorize)
    started = time.monotonic()
    deadline = payload.get('deadline_seconds', 0.3)
    con.set_progress_handler(lambda: int(time.monotonic() - started > deadline), 1000)
    try:
        cursor = con.execute(sql)  # sqlite3 rejects trailing additional statements.
        rows = cursor.fetchmany(1001)
        if len(rows) > 1000:
            return {'status': 'execution_error', 'error': 'Result row limit exceeded.'}
        return {'status': 'ok', 'columns': [x[0] for x in cursor.description], 'rows': rows}
    except sqlite3.Error as exc:
        message = str(exc)
        if any(t in message.lower() for t in ['not authorized', 'prohibited', 'readonly', 'one statement', 'no such function']):
            status = 'unsupported_query'
        elif 'syntax' in message.lower() or 'incomplete input' in message.lower() or 'unrecognized token' in message.lower():
            status = 'compilation_error'
        else:
            status = 'execution_error'
        # Do not echo query text or arbitrary identifiers into student feedback.
        return {'status': status, 'error': message[:250]}
    except (MemoryError, OverflowError):
        return {'status': 'execution_error', 'error': 'Resource limit exceeded.'}
    finally:
        con.close()


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin))))
    except Exception as exc:
        print(json.dumps({'status': 'execution_error', 'error': type(exc).__name__}))
