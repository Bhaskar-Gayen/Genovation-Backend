import re
import logging

logger = logging.getLogger("llama_formatter")


def clean_input(text: str) -> str:
    """Sanitize user input."""
    text = text.strip()
    
    text = re.sub(r"[\x00-\x1F\x7F]", "", text)
    return text


def format_for_llama(messages: list) -> str:
    """
    Format conversation history for LLaMA model on Replicate.
    Replicate LLaMA typically expects a single string prompt, not structured JSON.
    """
    conversation = []
    for msg in messages:
        role = "User" if msg.is_from_user else "Assistant"
        conversation.append(f"{role}: {msg.content}")
    
    return "\n".join(conversation)


def parse_llama_response(response: dict) -> str:
    """
    Extract the model's output from Replicate response.
    Usually, LLaMA returns output in `response['output'][0]`.
    """
    try:
        if "output" in response and response["output"]:
            return response["output"][0]
        return "[No response from LLaMA]"
    except Exception as e:
        logger.error(f"Failed to parse LLaMA response: {e}")
        return "[Malformed LLaMA response]"


def llama_error_message(error: Exception) -> str:
    """
    Human-readable error messages for LLaMA / Replicate.
    """
    msg = str(error).lower()
    if "quota" in msg:
        return "API quota exceeded. Please try again later."
    if "invalid" in msg and "api" in msg:
        return "Invalid Replicate API key. Contact support."
    if "timeout" in msg:
        return "Replicate API timeout. Please try again."
    return f"LLaMA API error: {error}"


def format_markdown(text: str) -> str:
    """Optional: convert model text to HTML if needed."""
    import markdown
    return markdown.markdown(text)
