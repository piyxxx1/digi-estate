import os
import difflib
import asyncio
import time
from google import genai
from google.genai import types

FILLER_WORDS = {"hmm", "haan", "acha", "achha", "ok", "okay", "yes", "yeah", "right", "hm", "hmmm", "ha", "theek", "thik", "oh", "accha", "hello", "hi", "kya", "ji"}

async def analyze_barge_in(text: str, bot_text: str, history_context: str = "") -> bool:
    """
    Returns True if this is a real interruption (stop bot), False if it should be ignored.
    Logs latency and LLM verdicts.
    """
    start_time = time.time()
    text_clean = text.strip().lower()
    import string
    text_no_punct = text_clean.translate(str.maketrans('', '', string.punctuation))
    words = text_no_punct.split()
    
    rule_result = "Pass"
    llm_result = "N/A"
    final_decision = False
    
    # Rule 1: Under 2 words
    if len(words) < 2:
        if len(words) == 1 and words[0] not in FILLER_WORDS:
            rule_result = "Reject (Short)"
        else:
            rule_result = "Reject (Short/Filler)"
            
    # Rule 2: Fillers
    elif all(w in FILLER_WORDS for w in words):
        rule_result = "Reject (Fillers)"
        
    # Rule 3: Echo (Fuzzy match with last 150 chars of bot)
    elif bot_text:
        bot_recent = bot_text[-150:].lower()
        ratio = difflib.SequenceMatcher(None, text_clean, bot_recent).ratio()
        if ratio > 0.6:
            rule_result = f"Reject (Echo: {ratio:.2f})"
    
    if rule_result != "Pass":
        latency = (time.time() - start_time) * 1000
        print(f"[Barge-In] Text: \"{text}\" | Rules: {rule_result} | LLM: skipped | Verdict: Ignored | Latency: {latency:.1f}ms")
        return False

    # LLM Classifier
    if os.getenv("BARGE_CLASSIFIER") == "1":
        try:
            model_name = os.getenv("BARGE_MODEL", "gemini-3.5-flash-lite")
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            prompt = f"""You are a voice assistant barge-in classifier. 
Recent Conversation Context:
{history_context}

Bot is currently speaking: "{bot_text}"
User interrupts by saying: "{text}"

Is this a real interruption where the user wants to take over the conversation or change the subject? 
If they are just acknowledging, agreeing, or saying something irrelevant, reply NO. 
If they are asking a new question, correcting you, or taking over, reply YES.
Reply ONLY with YES or NO."""
            
            async def call_llm():
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=5)
                )
                return response.text.strip().upper()

            res_text = await asyncio.wait_for(call_llm(), timeout=0.35)
            
            if "YES" in res_text:
                llm_result = "Interrupt"
                final_decision = True
            else:
                llm_result = "Ignore"
                final_decision = False
                
        except asyncio.TimeoutError:
            llm_result = "Timeout"
            final_decision = False # fail-safe
        except Exception as e:
            llm_result = f"Error: {str(e)}"
            final_decision = False
    else:
        final_decision = True
        
    latency = (time.time() - start_time) * 1000
    print(f"[Barge-In] Text: \"{text}\" | Rules: {rule_result} | LLM: {llm_result} | Verdict: {'Interrupted' if final_decision else 'Ignored'} | Latency: {latency:.1f}ms")
    return final_decision
