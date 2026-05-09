import os
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()


def get_bigquery_client():
    """Return an authenticated BigQuery client."""
    return bigquery.Client(project=os.getenv("BIGQUERY_PROJECT"))


def run_query(sql: str) -> list[dict]:
    """Execute a SQL query and return results as a list of dicts."""
    client = get_bigquery_client()
    query_job = client.query(sql)
    results = query_job.result()
    return [dict(row) for row in results]
