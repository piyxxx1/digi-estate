import os
from google import genai
from google.genai import types
from services.ai.prompt_builder import PromptBuilder
from models.request_models import ChatMessage
from typing import List, AsyncGenerator
import asyncio
from db.postgresql import fetch

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.fallback_model = "gemini-2.5-flash"    # Robust fallback
        self.prompt_builder = PromptBuilder()

    async def _get_properties_context(self) -> str:
        try:
            rows = await fetch("SELECT property_details FROM property ORDER BY id ASC;")
            if not rows:
                return "No properties currently listed."
            return "\n".join([f"- {dict(r)['property_details']}" for r in rows])
        except Exception as e:
            print(f"[Gemini Service] Warning: Failed to fetch properties context: {e}")
            return ""

    async def generate_response(self, user_message: str, history: List[ChatMessage]) -> str:
        try:
            valid_history = []
            for msg in history:
                valid_history.append(
                    types.Content(
                        role="user" if msg.role == "user" else "model",
                        parts=[types.Part(text=msg.text)]
                    )
                )
            
            if valid_history and valid_history[-1].role == "user":
                valid_history.pop()

            if valid_history and valid_history[0].role == "model":
                is_hindi = any(2304 <= ord(c) <= 2431 for c in user_message)
                dummy_text = "नमस्ते" if is_hindi else "Hello"
                valid_history.insert(0, types.Content(role="user", parts=[types.Part(text=dummy_text)]))

            final_prompt = self.prompt_builder.build_final_prompt(user_message)
            properties_context = await self._get_properties_context()
            sys_inst = self.prompt_builder.get_system_instruction(properties_context)

            try:
                # Try primary model first
                response = await self.client.aio.models.generate_content(
                    model=self.primary_model,
                    contents=valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)])],
                    config=types.GenerateContentConfig(
                        system_instruction=sys_inst
                    )
                )
                return response.text
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "resource exhausted" in str(e).lower():
                    print(f"[Gemini Service] Primary model {self.primary_model} overloaded. Falling back to {self.fallback_model}...")
                    response = await self.client.aio.models.generate_content(
                        model=self.fallback_model,
                        contents=valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)])],
                        config=types.GenerateContentConfig(
                            system_instruction=sys_inst
                        )
                    )
                    return response.text
                raise e

        except Exception as e:
            print(f"Gemini Service Error: {str(e)}")
            raise e

    async def generate_response_stream(self, user_message: str, history: List[ChatMessage]) -> AsyncGenerator[str, None]:
        """
        Generates streaming responses using configured Gemini streaming model.
        """
        valid_history = []
        for msg in history:
            valid_history.append(
                types.Content(
                    role="user" if msg.role == "user" else "model",
                    parts=[types.Part(text=msg.text)]
                )
            )
        
        if valid_history and valid_history[-1].role == "user":
            valid_history.pop()

        if valid_history and valid_history[0].role == "model":
            is_hindi = any(2304 <= ord(c) <= 2431 for c in user_message)
            dummy_text = "नमस्ते" if is_hindi else "Hello"
            valid_history.insert(0, types.Content(role="user", parts=[types.Part(text=dummy_text)]))

        final_prompt = self.prompt_builder.build_final_prompt(user_message)
        properties_context = await self._get_properties_context()
        sys_inst = self.prompt_builder.get_system_instruction(properties_context)
        yielded_any = False

        try:
            response_stream = await self.client.aio.models.generate_content_stream(
                model=self.primary_model,
                contents=valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)])],
                config=types.GenerateContentConfig(
                    system_instruction=sys_inst
                )
            )
            async for chunk in response_stream:
                if chunk.text:
                    yielded_any = True
                    yield chunk.text

        except Exception as e:
            if isinstance(e, asyncio.CancelledError):
                raise e
            
            err_str = str(e)
            if yielded_any:
                print(f"[Gemini Service Stream] Error mid-stream: {err_str}")
                raise e
                
            print(f"[Gemini Service Stream] Primary model {self.primary_model} failed ({type(e).__name__}: {err_str}). Falling back to {self.fallback_model}...")
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model=self.fallback_model,
                    contents=valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)])],
                    config=types.GenerateContentConfig(
                        system_instruction=sys_inst
                    )
                )
                async for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as fallback_err:
                print(f"[Gemini Service Stream] Fallback model also failed: {fallback_err}")
                raise fallback_err
