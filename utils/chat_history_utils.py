import json
import os

def load_history(filepath):
    """Load chat history from local JSON file."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading history from {filepath}: {e}")
        return {}

def save_history(filepath, history):
    """Save chat history to local JSON file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history to {filepath}: {e}")

def get_session_title(messages):
    """Generate a title for the session based on the first user message."""
    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"]
            if isinstance(content, list):
                for item in content:
                    if item["type"] == "text":
                        return item["text"][:20] + "..."
            else:
                return str(content)[:20] + "..."
    return "새로운 대화"
