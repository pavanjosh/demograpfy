from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

from agent.prompts import create_demografy_agent

# Per-user chat history store (lives for the server process lifetime)
_history_store: dict[str, ChatMessageHistory] = {}

_WINDOW_SIZE = 5  # number of past exchanges to keep in context


def get_history(user_id: str) -> ChatMessageHistory:
    if user_id not in _history_store:
        _history_store[user_id] = ChatMessageHistory()
    return _history_store[user_id]


def seed_memory_from_history(user_id: str, chat_history: list[dict]):
    """
    Populate in-memory history from the persisted JSON chat log on first load.
    Skipped if messages are already loaded for this user.
    """
    history = get_history(user_id)
    if history.messages:
        return

    # Pair up user/assistant turns
    pairs: list[dict] = []
    pending_user: str | None = None
    for msg in chat_history:
        if msg["role"] == "user":
            pending_user = msg["content"]
        elif msg["role"] == "assistant" and pending_user is not None:
            pairs.append({"user": pending_user, "ai": msg["content"]})
            pending_user = None

    # Seed only the last _WINDOW_SIZE exchanges to keep context tight
    for pair in pairs[-_WINDOW_SIZE:]:
        history.add_user_message(pair["user"])
        history.add_ai_message(pair["ai"])


def _build_context_block(user_id: str) -> str:
    """Return a plain-text summary of recent conversation, or empty string."""
    messages = get_history(user_id).messages
    # Keep only the last _WINDOW_SIZE exchanges (2 messages each)
    recent = messages[-(  _WINDOW_SIZE * 2):]

    lines: list[str] = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Assistant: {msg.content}")

    return "\n".join(lines)


def ask_question_with_memory(
    user_id: str,
    question: str,
    chat_history: list[dict] | None = None,
) -> str:
    """
    Submit a question to the SQL agent with previous conversation context injected.

    On the first call for a user the memory is seeded from the persisted
    chat_history list (list of {"role": ..., "content": ...} dicts).
    Subsequent calls within the same server session reuse the in-memory store.
    """
    # Seed from disk on first call
    if chat_history:
        seed_memory_from_history(user_id, chat_history)

    # Prepend conversation history to the question
    context_block = _build_context_block(user_id)
    if context_block:
        enriched_question = (
            f"Previous conversation:\n{context_block}\n\n"
            f"Current question: {question}"
        )
    else:
        enriched_question = question

    # Run the agent
    agent = create_demografy_agent()
    try:
        result = agent.invoke({"input": enriched_question})
        answer = result.get("output", "Sorry, I couldn't generate an answer.")
    except Exception as e:
        answer = f"An error occurred while processing your question: {str(e)}"

    # Save this exchange to memory
    history = get_history(user_id)
    history.add_user_message(question)
    history.add_ai_message(answer)

    return answer


def clear_memory(user_id: str):
    """Drop conversation memory for a user (called on chat reset)."""
    _history_store.pop(user_id, None)