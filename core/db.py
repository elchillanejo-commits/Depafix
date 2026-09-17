import os, psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    return psycopg2.connect(
        host="localhost", user="depafix", dbname="depafix",
        password=os.environ.get("PGPASSWORD", "sGXizxWs4khbF8ZJeOJ"),
        cursor_factory=RealDictCursor
    )
