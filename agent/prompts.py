_FALLBACK_PREFIX = """You are a demographic data analyst for Demografy.
You query Australian demographic data from BigQuery.

TABLE: demografy.prod_tables.a_master_view

KEY COLUMN MAPPINGS (always use these exact column names):
- "suburb" or "area" or "location" = sa2_name
- "state" or "territory" = state
- "population" = population
- "prosperity score" or "prosperity" = kpi_1_val (range: 0-100%)
- "diversity index" or "diversity" = kpi_2_val (range: 0-1)
- "migration footprint" or "migration" = kpi_3_val (range: 0-100%)
- "learning level" or "education level" or "education" = kpi_4_val (range: 0-100%)
- "social housing" = kpi_5_val (range: 0-100%)
- "resident equity" or "home ownership" or "ownership" = kpi_6_val (range: 0-100%)
- "rental access" or "rental affordability" or "affordability" = kpi_7_val (range: 0-100%)
- "resident anchor" or "stability" or "community stability" = kpi_8_val (range: 0-100%)
- "household mobility" or "mobility potential" = kpi_9_val (range: 0-1)
- "young family" or "young families" or "family indicator" = kpi_10_val (range: 0-100%)

IMPORTANT RULES:
- ALWAYS use the fully qualified table name: demografy.prod_tables.a_master_view
- NEVER run DELETE, UPDATE, INSERT, or DROP statements
- LIMIT results to 50 rows maximum unless the user specifies otherwise
- Use descriptive column aliases in SELECT statements (e.g., AS diversity_index)
- In ORDER BY clauses, always use the full expression (e.g., ORDER BY AVG(kpi_4_val) DESC), NEVER an alias name
- NEVER call sql_db_schema — all column names are already defined in KEY COLUMN MAPPINGS above
- State values are written as full names: 'Victoria', 'New South Wales', 'Queensland',
  'South Australia', 'Western Australia', 'Tasmania', 'Northern Territory',
  'Australian Capital Territory'

MANDATORY EXECUTION STEPS (follow these in order for every question):
1. Write the SQL query using KEY COLUMN MAPPINGS above — do NOT call sql_db_schema.
2. Use sql_db_query_checker to validate your SQL query.
3. You MUST then call sql_db_query to actually execute the validated query and retrieve real data.
4. Only return a final answer AFTER you have received real query results from sql_db_query.
   Never return a final answer based only on the query checker output — that is not data.

EXAMPLE QUERIES:

Q: Top 3 most diverse suburbs in Victoria
SQL: SELECT sa2_name, state, kpi_2_val AS diversity_index
     FROM demografy.prod_tables.a_master_view
     WHERE state = 'Victoria'
     ORDER BY kpi_2_val DESC
     LIMIT 3;

Q: Average prosperity score in New South Wales
SQL: SELECT AVG(kpi_1_val) AS avg_prosperity_score
     FROM demografy.prod_tables.a_master_view
     WHERE state = 'New South Wales';

Q: Which state has the highest average education level
SQL: SELECT state, AVG(kpi_4_val) AS avg_learning_level
     FROM demografy.prod_tables.a_master_view
     GROUP BY state
     ORDER BY AVG(kpi_4_val) DESC
     LIMIT 1;

Q: Suburbs with high young family presence (over 25%) and high learning level (over 70%)
SQL: SELECT sa2_name, state, kpi_10_val AS young_family_pct, kpi_4_val AS learning_level
     FROM demografy.prod_tables.a_master_view
     WHERE kpi_10_val > 25 AND kpi_4_val > 70
     ORDER BY kpi_10_val DESC
     LIMIT 20;

Q: Most stable suburbs in Queensland
SQL: SELECT sa2_name, kpi_8_val AS resident_anchor
     FROM demografy.prod_tables.a_master_view
     WHERE state = 'Queensland'
     ORDER BY kpi_8_val DESC
     LIMIT 10;

Q: Compare home ownership vs rental access by state
SQL: SELECT state,
            AVG(kpi_6_val) AS avg_resident_equity,
            AVG(kpi_7_val) AS avg_rental_access
     FROM demografy.prod_tables.a_master_view
     GROUP BY state
     ORDER BY AVG(kpi_6_val) DESC;

Q: Suburbs with high social housing in Victoria
SQL: SELECT sa2_name, kpi_5_val AS social_housing_pct
     FROM demografy.prod_tables.a_master_view
     WHERE state = 'Victoria' AND kpi_5_val > 20
     ORDER BY kpi_5_val DESC
     LIMIT 20;

Q: Most affordable rental suburbs in Queensland
SQL: SELECT sa2_name, kpi_7_val AS rental_access
     FROM demografy.prod_tables.a_master_view
     WHERE state = 'Queensland'
     ORDER BY kpi_7_val DESC
     LIMIT 10;
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _load_prefix() -> str:
    repo = os.getenv("LANGCHAIN_PROMPT_REPO")
    if not repo:
        return _FALLBACK_PREFIX
    version = os.getenv("LANGCHAIN_PROMPT_VERSION", "")
    ref = f"{repo}:{version}" if version else repo
    try:
        from langsmith import Client
        prompt = Client().pull_prompt(ref)
        print(f"[prompts] Loaded prompt from hub: {ref}")
        return prompt.template
    except Exception as e:
        print(f"[prompts] Hub pull failed ({e}), using fallback.")
        return _FALLBACK_PREFIX


FEW_SHOT_PREFIX = _load_prefix()


### agent setup
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI

_agent = None  # Module-level cache so we only create the agent once


def create_demografy_agent():
    """Create and return the LangChain SQL agent."""
    global _agent
    if _agent is not None:
        return _agent

    # Connect to BigQuery via LangChain
    db = SQLDatabase.from_uri(
        f"bigquery://{os.getenv('BIGQUERY_PROJECT')}/prod_tables",
        include_tables=["a_master_view"],
    )

    # LangChain validates table names in sql_db_schema against include_tables.
    # The agent uses the fully qualified name in SQL, so we register it as an alias
    # to prevent "table not found" errors when the agent calls sql_db_schema.
    project = os.getenv("BIGQUERY_PROJECT", "demografy")
    fq_name = f"{project}.prod_tables.a_master_view"
    simple_schema = db.get_table_info(["a_master_view"])
    db._include_tables.add(fq_name)
    if db._custom_table_info is None:
        db._custom_table_info = {}
    db._custom_table_info[fq_name] = simple_schema

    # Set up Gemini as the LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0,  # Keep deterministic for SQL generation
    )

    agent_suffix = (
        "CRITICAL REMINDER: You are not done until you have called sql_db_query "
        "and received real rows from the database. "
        "After sql_db_list_tables or sql_db_query_checker you MUST continue and "
        "call sql_db_query next. Never produce a final answer before executing the query."
    )

    # Create the SQL agent with our few-shot prefix
    _agent = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="openai-tools",
        prefix=FEW_SHOT_PREFIX,
        suffix=agent_suffix,
        verbose=True,
        max_iterations=15,
        handle_parsing_errors=True,
    )
    return _agent


def ask_question(question: str) -> str:
    """
    Submit a natural language question to the agent and return a text answer.
    """
    agent = create_demografy_agent()
    try:
        response = agent.invoke({"input": question})
        return response.get("output", "Sorry, I couldn't generate an answer.")
    except Exception as e:
        return f"An error occurred while processing your question: {str(e)}"

# response = ask_question("What are the top 5 most prosperous suburbs in New South Wales?")
# response = ask_question("Which is the cheapest suburb in Queensland with a high young family presence (over 30%)?")
# response = ask_question("Which state has the highest average resident equity?")
# response = ask_question("List me some cheap rental suburbs in New South Wales with high social housing (over 15%)")
# print(response)
# response = ask_question("What are the top 5 suburbs in Victoria with the highest rental access?")