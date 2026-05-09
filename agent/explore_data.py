from bigquery_client import run_query

# Check what state values actually look like
states = run_query(
    """
    SELECT DISTINCT state, COUNT(*) as suburb_count
    FROM demografy.prod_tables.a_master_view
    GROUP BY state
    ORDER BY suburb_count DESC
"""
)
print("STATES:", states)

# Check KPI ranges
ranges = run_query(
    """
    SELECT
        MIN(kpi_1_val) as min_prosperity, MAX(kpi_1_val) as max_prosperity,
        MIN(kpi_2_val) as min_diversity, MAX(kpi_2_val) as max_diversity,
        MIN(population) as min_pop, MAX(population) as max_pop
    FROM demografy.prod_tables.a_master_view
"""
)
print("RANGES:", ranges)

# Check for nulls
nulls = run_query(
    """
    SELECT
        COUNTIF(kpi_1_val IS NULL) as null_prosperity,
        COUNTIF(kpi_2_val IS NULL) as null_diversity,
        COUNT(*) as total_rows
    FROM demografy.prod_tables.a_master_view
"""
)
print("NULLS:", nulls)
