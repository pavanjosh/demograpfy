#!/usr/bin/env python3
"""
One-time script to push the current prompt to LangSmith Hub.

Usage:
    python agent/push_prompt.py

After running, copy the printed version hash into your .env:
    LANGCHAIN_PROMPT_VERSION=<hash>

To push a new version later, edit _FALLBACK_PREFIX in prompts.py and run again.
"""
import os
import sys

# Ensure project root is on the path so `agent` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Validate required env vars before importing hub
if not os.getenv("LANGCHAIN_API_KEY"):
    sys.exit("Error: LANGCHAIN_API_KEY is not set in .env")

repo = os.getenv("LANGCHAIN_PROMPT_REPO")
if not repo:
    sys.exit(
        "Error: LANGCHAIN_PROMPT_REPO is not set in .env\n"
        "Set it to just a repo name, e.g.: demografy-sql-prefix\n"
        "LangSmith will infer the org from your API key automatically."
    )

from langsmith import Client
from langchain_core.prompts import PromptTemplate
from agent.prompts import _FALLBACK_PREFIX

client = Client()
prompt = PromptTemplate.from_template(_FALLBACK_PREFIX)

print(f"Pushing prompt to hub repo: {repo} ...")
url = client.push_prompt(repo, object=prompt)

# LangSmith returns a URL like https://smith.langchain.com/prompts/<repo>/commits/<hash>
version_hash = url.rstrip("/").split("/")[-1]

print(f"\nPushed successfully.")
print(f"Hub URL   : {url}")
print(f"Version   : {version_hash}")
print(f"\nTo pin to this version, add to your .env:")
print(f"  LANGCHAIN_PROMPT_VERSION={version_hash}")