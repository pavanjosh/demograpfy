from agent.bigquery_client import run_query


def verify_user(user_id: str, email: str) -> dict | None:
    """
    Returns the user record (user_id, email, tier) if a matching
    active account exists in BigQuery, otherwise returns None.
    """
    sql = f"""
        SELECT user_id, email, tier
        FROM `demografy.ref_tables.dev_customers`
        WHERE LOWER(user_id) = LOWER('{user_id}')
          AND LOWER(email) = LOWER('{email}')
          AND is_active = true
        LIMIT 1
    """
    results = run_query(sql)
    return results[0] if results else None
