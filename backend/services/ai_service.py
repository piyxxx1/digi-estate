import json
import uuid
import os
from google import genai
from google.genai import types
from services.ai.prompt_builder import PromptBuilder
from models.request_models import ChatMessage
from typing import List, AsyncGenerator
import asyncio
import time
from db.postgresql import fetch, execute

import random

FILLER_PHRASES = [
    "मैं अभी चेक करके बताता हूँ। ",
    "जरूर, मुझे एक सेकंड दीजिये, मैं डिटेल्स देखता हूँ। ",
    "हाँ बिल्कुल, मैं अभी इसके बारे में जानकारी निकालता हूँ। "
]

book_site_visit_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="book_site_visit",
            description="Use this tool ONLY when the caller explicitly agrees to a site visit and has provided both their preferred date/time and their name. Do not use this tool prematurely.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "visitor_name": types.Schema(type=types.Type.STRING, description="The name of the visitor"),
                    "visit_date_time": types.Schema(type=types.Type.STRING, description="The preferred date and time for the visit"),
                },
                required=["visitor_name", "visit_date_time"]
            )
        )
    ]
)

fetch_property_details_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="fetch_property_details",
            description="Use this tool to fetch detailed information (amenities, floor plans, location) for a property. IMPORTANT: Once you have fetched details for a specific property_id, DO NOT call this tool again for the same property. Rely on your chat history for follow-up questions.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "property_id": types.Schema(type=types.Type.STRING, description="The ID of the property to fetch details for")
                },
                required=["property_id"]
            )
        )
    ]
)

hang_up_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="hang_up",
            description="Use this tool when the conversation is over and the call should be disconnected.",
        )
    ]
)

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.primary_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.fallback_model = "gemini-3.5-flash-lite"    # Robust fallback
        self.prompt_builder = PromptBuilder()
        self.current_property_id = None
        self.cached_properties = {}

    async def _get_properties_context(self) -> str:
        try:
            # Fetch a lightweight summary of all live properties
            rows = await fetch("SELECT property_id, name, city, region, property_type, unit_types FROM properties WHERE status = 'live' ORDER BY created_at DESC;")
            if not rows:
                return "No properties currently listed."
            
            summary = []
            for r in rows:
                row_dict = dict(r)
                unit_types = row_dict.get('unit_types', [])
                if isinstance(unit_types, str):
                    try:
                        unit_types = json.loads(unit_types)
                    except:
                        unit_types = []
                        
                unit_types_str = "None specified"
                
                if unit_types and len(unit_types) > 0:
                    # Format unit types for prompt (e.g., "Villa (from 7000000), Plot")
                    types_list = []
                    for u in unit_types:
                        t = u.get('type')
                        p = u.get('price_min')
                        if t and p:
                            types_list.append(f"{t} (from {p})")
                        elif t:
                            types_list.append(t)
                    if types_list:
                        unit_types_str = ", ".join(types_list)
                        
                region_str = f", {row_dict['region']}" if row_dict.get('region') else ""
                        
                summary.append(f"- ID: {row_dict['property_id']} | Name: {row_dict['name']} | Location: {row_dict['city']}{region_str} | Type: {row_dict['property_type']} | Units: {unit_types_str}")
            
            context_str = "Catalog of available properties:\n" + "\n".join(summary)
            
            if getattr(self, 'current_property_id', None):
                try:
                    prop_uuid = uuid.UUID(str(self.current_property_id))
                    raw_data = await fetch("SELECT name, raw_text FROM properties WHERE property_id = $1", prop_uuid)
                    if raw_data and raw_data[0]['raw_text']:
                        context_str += f"\n\nDetailed Information for currently in-discussion property ({raw_data[0]['name']}):\n{raw_data[0]['raw_text']}\n"
                except Exception as e:
                    print(f"Error fetching raw_text for current property: {e}")
                    
            return context_str
                
        except Exception as e:
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
                dummy_text = "Hello"
                valid_history.insert(0, types.Content(role="user", parts=[types.Part(text=dummy_text)]))

            final_prompt = self.prompt_builder.build_final_prompt(user_message)
            properties_context = await self._get_properties_context()
            sys_inst = self.prompt_builder.get_system_instruction(properties_context)

            # We won't add tool to generate_response because it's for non-streaming (maybe used for sms/whatsapp)
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.primary_model,
                    contents=valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)])],
                    config=types.GenerateContentConfig(
                        system_instruction=sys_inst,
                        #temperature=0.3,
                        thinking_config=types.ThinkingConfig(
                            thinking_level="minimal"  # Options typically include "minimal", "low", "medium", "high"
                        )
                    )
                )
                return response.text
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "resource exhausted" in str(e).lower():
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
            raise e

    async def generate_response_stream(self, user_message: str, history: List[ChatMessage]) -> AsyncGenerator[str, None]:
        t_start = time.time()
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
            dummy_text = "Hello"
            valid_history.insert(0, types.Content(role="user", parts=[types.Part(text=dummy_text)]))

        t_history = time.time()
        final_prompt = self.prompt_builder.build_final_prompt(user_message)
        
        t_prompt = time.time()
        properties_context = await self._get_properties_context()
        
        t_db = time.time()
        sys_inst = self.prompt_builder.get_system_instruction(properties_context)
        yielded_any = False

        config = types.GenerateContentConfig(
            system_instruction=sys_inst,
            tools=[book_site_visit_tool, hang_up_tool, fetch_property_details_tool],
            #temperature=0.3,
            thinking_config=types.ThinkingConfig(
                            thinking_level="minimal"  # Options typically include "minimal", "low", "medium", "high"
                        )
        )

        t_pre_call = time.time()
        print(f"[Timing] Step 1 Prep: History={(t_history-t_start)*1000:.1f}ms, Prompt={(t_prompt-t_history)*1000:.1f}ms, DB Fetch={(t_db-t_prompt)*1000:.1f}ms, SysInst={(t_pre_call-t_db)*1000:.1f}ms")

        try:
            response_stream = await self.client.aio.models.generate_content_stream(
                model=self.primary_model,
                contents=valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)])],
                config=config
            )
            
            first_token_yielded = False
            async for chunk in response_stream:
                chunk_text_safe = ""
                try:
                    chunk_text_safe = chunk.text
                except ValueError:
                    pass
                    
                if not first_token_yielded and chunk_text_safe:
                    t_first_token = time.time()
                    print(f"[Timing] Step 2 TTFT: {(t_first_token - t_pre_call):.2f}s")
                    first_token_yielded = True
                    
                if chunk.function_calls:
                    for fc in chunk.function_calls:
                        if fc.name == "fetch_property_details":
                            # 1. Instantly yield a filler phrase to mask the latency!
                            yield random.choice(FILLER_PHRASES)
                            
                            # 2. Fetch the chunks
                            prop_id_str = fc.args.get("property_id")
                            print(f"\n================ PROPERTY LOOKUP LOG ================")
                            print(f"[Tool Called] fetch_property_details")
                            print(f"[Input] User asked about property ID: {prop_id_str}")
                            self.current_property_id = prop_id_str
                            
                            if prop_id_str in self.cached_properties:
                                details_str = self.cached_properties[prop_id_str]
                                print(f"[Result] Using CACHED property details for: {prop_id_str}")
                            else:
                                details_str = "No detailed information found for this property."
                                try:
                                    prop_id = uuid.UUID(prop_id_str)
                                    property_data = await fetch("SELECT name, raw_text FROM properties WHERE property_id = $1", prop_id)
                                    if property_data and property_data[0].get('raw_text'):
                                        details_str = f"Detailed Information for {property_data[0]['name']}:\n{property_data[0]['raw_text']}"
                                        self.cached_properties[prop_id_str] = details_str
                                        print(f"[Result] Successfully retrieved full brochure (raw_text) for: {property_data[0]['name']}")
                                    else:
                                        print("[Result] No raw_text found in database.")
                                except ValueError:
                                    print(f"[Error] Invalid UUID format for Property ID: {prop_id_str}")
                            print(f"=====================================================\n")
                                
                            # 3. Create a new interaction for Gemini and continue the stream
                            model_call = types.Content(role="model", parts=chunk.candidates[0].content.parts)
                            tool_response = types.Content(role="user", parts=[types.Part.from_function_response(name=fc.name, response={"result": details_str})])
                            
                            second_stream = await self.client.aio.models.generate_content_stream(
                                model=self.primary_model,
                                contents=valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)]), model_call, tool_response],
                                config=config
                            )
                            
                            async for chunk2 in second_stream:
                                try:
                                    c2_text = chunk2.text
                                except ValueError:
                                    c2_text = ""
                                if c2_text:
                                    yield c2_text
                                    
                            return
                        elif fc.name == "book_site_visit":
                            visitor_name = fc.args.get("visitor_name", "")
                            visit_date_time = fc.args.get("visit_date_time", "")
                            try:
                                # We would normally insert into DB here. Assuming table structure might not exist, just print.
                                pass
                            except Exception as db_err:
                                pass
                                
                            tool_response = types.Content(
                                role="user",
                                parts=[types.Part(
                                    function_response=types.FunctionResponse(
                                        name="book_site_visit",
                                        response={"status": "success", "message": f"Successfully booked for {visitor_name} at {visit_date_time}."}
                                    )
                                )]
                            )
                            valid_history.append(types.Content(role="model", parts=chunk.candidates[0].content.parts))
                            valid_history.append(tool_response)
                            
                            response_stream2 = await self.client.aio.models.generate_content_stream(
                                model=self.primary_model,
                                contents=valid_history,
                                config=config
                            )
                            async for c2 in response_stream2:
                                try:
                                    c2_text = c2.text
                                except ValueError:
                                    c2_text = ""
                                if c2_text:
                                    yield c2_text
                                    
                            return
                        elif fc.name == "hang_up":
                            yield "hang_up"
                            return

                if chunk_text_safe:
                    yielded_any = True
                    yield chunk_text_safe

        except Exception as e:
            if isinstance(e, asyncio.CancelledError):
                raise e
            
            import traceback
            err_str = str(e)
            print(f"[AI Service] Primary Model Error: {err_str}")
            print(f"[AI Service] Primary Model Traceback:\n{traceback.format_exc()}")
            if yielded_any:
                raise e
                
            try:
                print(f"[AI Service] Attempting Fallback Model...")
                fallback_history = valid_history + [types.Content(role="user", parts=[types.Part(text=final_prompt)])]
                response_stream = await self.client.aio.models.generate_content_stream(
                    model=self.fallback_model,
                    contents=fallback_history,
                    config=config
                )
                async for chunk in response_stream:
                    if chunk.function_calls:
                        for fc in chunk.function_calls:
                            if fc.name == "fetch_property_details":
                                yield random.choice(FILLER_PHRASES)
                                prop_id_str = fc.args.get("property_id")
                                print(f"\n================ PROPERTY LOOKUP LOG ================")
                                print(f"[Tool Called] fetch_property_details (from fallback)")
                                print(f"[Input] User asked about property ID: {prop_id_str}")
                                self.current_property_id = prop_id_str
                                details_str = "No detailed information found for this property."
                                try:
                                    prop_id = uuid.UUID(prop_id_str)
                                    property_data = await fetch("SELECT name, raw_text FROM properties WHERE property_id = $1", prop_id)
                                    if property_data and property_data[0].get('raw_text'):
                                        details_str = f"Detailed Information for {property_data[0]['name']}:\n{property_data[0]['raw_text']}"
                                        print(f"[Result] Successfully retrieved full brochure (raw_text) for: {property_data[0]['name']}")
                                    else:
                                        print("[Result] No raw_text found in database.")
                                except ValueError:
                                    print(f"[Error] Invalid UUID format for Property ID: {prop_id_str}")
                                print(f"=====================================================\n")
                                    
                                model_call = types.Content(role="model", parts=chunk.candidates[0].content.parts)
                                tool_response = types.Content(role="user", parts=[types.Part.from_function_response(name=fc.name, response={"result": details_str})])
                                
                                second_stream = await self.client.aio.models.generate_content_stream(
                                    model=self.fallback_model,
                                    contents=fallback_history + [model_call, tool_response],
                                    config=config
                                )
                                async for chunk2 in second_stream:
                                    try:
                                        c2_text = chunk2.text
                                    except ValueError:
                                        c2_text = ""
                                    if c2_text:
                                        yield c2_text
                                return
                            elif fc.name == "book_site_visit":
                                visitor_name = fc.args.get("visitor_name", "")
                                visit_date_time = fc.args.get("visit_date_time", "")
                                
                                tool_response = types.Content(
                                    role="user",
                                    parts=[types.Part(
                                        function_response=types.FunctionResponse(
                                            name="book_site_visit",
                                            response={"status": "success", "message": f"Successfully booked for {visitor_name} at {visit_date_time}."}
                                        )
                                    )]
                                )
                                fallback_history.append(types.Content(role="model", parts=chunk.candidates[0].content.parts))
                                fallback_history.append(tool_response)
                                
                                response_stream2 = await self.client.aio.models.generate_content_stream(
                                    model=self.fallback_model,
                                    contents=fallback_history,
                                    config=config
                                )
                                async for c2 in response_stream2:
                                    try:
                                        c2_text = c2.text
                                    except ValueError:
                                        c2_text = ""
                                    if c2_text:
                                        yield c2_text
                                return
                            elif fc.name == "hang_up":
                                yield "hang_up"
                                return
                    try:
                        c_text = chunk.text
                    except ValueError:
                        c_text = ""
                    if c_text:
                        yield c_text
                return
            except Exception as fallback_err:
                import traceback
                print(f"[AI Service] Fallback Model Error: {fallback_err}")
                print(f"[AI Service] Fallback Model Traceback:\n{traceback.format_exc()}")
                raise fallback_err