import os
import json
from dotenv import load_dotenv

load_dotenv()

_JUDGE_PROMPT = """You are evaluating an AI assistant that answers questions about Australian demographic data.

Compare the actual response against the golden (expected) answer and score it.

Score using this rubric:
5 = perfect match with correct data
4 = correct data, minor formatting issues
3 = mostly correct, small discrepancies
2 = partially correct, significant errors
1 = wrong answer or failed to execute

Question: {question}

Golden Answer (expected): {golden_answer}

Actual Response: {answer}

Return ONLY valid JSON in this exact format, no extra text:
{{
  "score": <1-5>,
  "relevance": "<did it answer the question?>",
  "groundedness": "<is it based on real data or hallucinated?>",
  "completeness": "<is anything missing?>",
  "reasoning": "<one sentence overall verdict>"
}}"""

_JUDGE_PROMPT_NO_GOLDEN = """You are evaluating an AI assistant that answers questions about Australian demographic data.

Score the response using this rubric:
5 = perfect match with correct data
4 = correct data, minor formatting issues
3 = mostly correct, small discrepancies
2 = partially correct, significant errors
1 = wrong answer or failed to execute

Question: {question}

Response: {answer}

Return ONLY valid JSON in this exact format, no extra text:
{{
  "score": <1-5>,
  "relevance": "<did it answer the question?>",
  "groundedness": "<is it based on real data or hallucinated?>",
  "completeness": "<is anything missing?>",
  "reasoning": "<one sentence overall verdict>"
}}"""


def judge_response(question: str, answer: str, golden_answer: str | None = None) -> dict:
    """
    Judge an agent response using Gemini. Compares against golden_answer when provided.
    Returns a dict with score and breakdown.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0,
    )

    if golden_answer:
        prompt = _JUDGE_PROMPT.format(
            question=question, golden_answer=golden_answer, answer=answer
        )
    else:
        prompt = _JUDGE_PROMPT_NO_GOLDEN.format(question=question, answer=answer)

    result = llm.invoke(prompt)
    raw = result.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "score": 0,
            "relevance": "parse error",
            "groundedness": "parse error",
            "completeness": "parse error",
            "reasoning": f"Judge returned unparseable output: {raw[:200]}",
        }