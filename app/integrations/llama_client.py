import os
import replicate
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class LlamaClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("REPLICATE_API_TOKEN")
        if not self.api_key:
            raise ValueError("Missing Replicate API key. Set REPLICATE_API_TOKEN in your environment.")
        os.environ["REPLICATE_API_TOKEN"] = self.api_key

        self.model = "meta/llama-4-maverick-instruct"

    async def send_prompt(self, prompt: str, context: str = "", max_tokens: int = 500, temperature: float = 0.7) -> str:
        try:
            loop = asyncio.get_running_loop()
            output = await loop.run_in_executor(
                None,
                lambda: replicate.run(
                    f"{self.model}",
                    input={
                        "prompt": f"{context}\nUser: {prompt}\nAssistant:",
                        "max_new_tokens": max_tokens,
                        "temperature": temperature,
                    },
                    timeout=60
                )
            )

            if not output:
                logger.warning("Empty response from Llama.")
                return ""

            # Ensure we return a string
            if isinstance(output, list):
                return "".join(output).strip()
            elif isinstance(output, str):
                return output.strip()
            else:
                return ""

        except Exception as e:
            logger.error(f"Llama API call failed: {e}", exc_info=True)
            return ""