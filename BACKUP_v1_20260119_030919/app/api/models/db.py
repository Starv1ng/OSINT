# services/api/app/api/models/db.py
from sqlalchemy import create_engine, MetaData, Table, Column, String, Text, Float, JSON, TIMESTAMP
from sqlalchemy.sql import func
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://dev:devpass@postgres:5432/osint")
engine = create_engine(DATABASE_URL)
metadata = MetaData()

JobsTable = Table(
    "jobs",
    metadata,
    Column("job_id", String, primary_key=True),
    Column("requester_id", String),
    Column("input_type", String, nullable=False),
    Column("input_value", Text, nullable=False),
    Column("status", String, nullable=False, default="accepted"),
    Column("progress", Float, default=0.0),
    Column("result", JSON),
    Column("created_at", TIMESTAMP, server_default=func.now()),
    Column("updated_at", TIMESTAMP, server_default=func.now()),
)

def create_tables():
    metadata.create_all(engine)

def get_session():
    return engine.connect()