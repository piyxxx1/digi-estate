import asyncio
import os
import re
from typing import AsyncIterator

MARKDOWN_RE = re.compile(r'[*_#`]')
EMOJI_RE = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

SENTENCE_ENDERS = {'।', '?', '!', '.', '॥'}
CLAUSE_BREAKERS = {',', ';', ':', '—', '-'}
CONJUNCTIONS = {"और", "लेकिन", "क्योंकि", "तो", "कि", "and", "but"}
TITLES = {"dr", "mr", "mrs", "ms", "prof", "sr", "jr", "rs", "vs"}

def clean_text(text: str) -> str:
    text = MARKDOWN_RE.sub('', text)
    text = EMOJI_RE.sub('', text)
    text = CONTROL_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_best_split(text: str, max_limit: int) -> tuple[int, int]:
    limit = min(len(text), max_limit)
    in_parens = 0
    in_quotes = False
    best_idx = -1
    best_score = -999
    
    for i in range(limit):
        c = text[i]
        if c in ('(', '[', '{'): in_parens += 1
        elif c in (')', ']', '}'): in_parens = max(0, in_parens - 1)
        elif c in ('"', "'"): in_quotes = not in_quotes
        
        score = -1
        
        if c in SENTENCE_ENDERS:
            if c == '.':
                left_part = text[:i].rstrip()
                last_word = left_part.split()[-1].lower() if left_part else ""
                if last_word in TITLES:
                    pass
                else:
                    nc = ''
                    for j in range(i+1, len(text)):
                        if not text[j].isspace():
                            nc = text[j]
                            break
                    if nc:
                        if nc.isdigit() or (nc.islower() and 'a' <= nc <= 'z'):
                            pass
                        else:
                            score = 3
                    else:
                        score = 3
            else:
                score = 3
        elif c in CLAUSE_BREAKERS:
            if c in (',', ':') and i + 1 < len(text) and text[i+1].isdigit():
                pass
            else:
                score = 2
        elif c.isspace():
            score = 0
            left_part = text[:i].rstrip()
            if left_part:
                last_word = left_part.split()[-1].lower()
                if last_word in CONJUNCTIONS:
                    score = 1
                    
        if score != -1:
            adjusted_score = score
            if in_parens > 0 or in_quotes:
                adjusted_score -= 10
            if adjusted_score >= best_score:
                best_score = adjusted_score
                best_idx = i + 1
                
    return best_idx, best_score

async def chunk_for_tts(
    source: AsyncIterator[str], 
    *, 
    first_min_chars: int = None,
    min_chars: int = None,
    max_chars: int = None,
    idle_flush_ms: int = None
) -> AsyncIterator[str]:
    
    first_min_chars = first_min_chars if first_min_chars is not None else int(os.getenv("TTS_CHUNK_FIRST_MIN", "25"))
    min_chars = min_chars if min_chars is not None else int(os.getenv("TTS_CHUNK_MIN", "60"))
    max_chars = max_chars if max_chars is not None else int(os.getenv("TTS_CHUNK_MAX", "140"))
    idle_flush_ms = idle_flush_ms if idle_flush_ms is not None else int(os.getenv("TTS_CHUNK_IDLE_MS", "400"))
    
    debug_log = os.getenv("TTS_CHUNK_DEBUG", "0") == "1" or os.getenv("DEBUG_AUDIO", "1") == "1"
    
    buffer = ""
    is_first = True
    chunk_index = 0
    t_start = asyncio.get_event_loop().time()
    
    # Safe queueing to avoid cancelling generator __anext__
    q = asyncio.Queue()
    async def feeder():
        try:
            async for chunk in source:
                await q.put(chunk)
            await q.put(None) # EOF sentinel
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await q.put(e)
            
    feeder_task = asyncio.create_task(feeder())
    
    def log_chunk(chunk: str):
        nonlocal chunk_index, is_first, t_start
        if not debug_log:
            return
        try:
            from api.websocket.exotel_ws import get_boundary_ts
            ts = get_boundary_ts()
        except Exception:
            import datetime
            ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        info = f"len={len(chunk)}"
        if is_first:
            info += f", delay={(asyncio.get_event_loop().time() - t_start)*1000:.1f}ms"
            is_first = False
        print(f"[{ts}] [Boundary] TTS Chunker emited chunk #{chunk_index}: {info}")
        chunk_index += 1

    try:
        while True:
            try:
                token = await asyncio.wait_for(q.get(), timeout=idle_flush_ms / 1000.0)
                if token is None:
                    break
                if isinstance(token, Exception):
                    raise token
                buffer += token
            except asyncio.TimeoutError:
                if len(buffer.strip()) > 0:
                    idx, score = get_best_split(buffer, len(buffer))
                    if idx > 0 and score >= 0:
                        chunk = clean_text(buffer[:idx])
                        buffer = buffer[idx:]
                        if chunk:
                            log_chunk(chunk)
                            yield chunk
                continue
                
            while True:
                target_min = first_min_chars if is_first else min_chars
                if len(buffer) >= max_chars:
                    idx, score = get_best_split(buffer, max_chars)
                    if idx <= 0:
                        idx = max_chars
                    chunk = clean_text(buffer[:idx])
                    buffer = buffer[idx:]
                    if chunk:
                        log_chunk(chunk)
                        yield chunk
                    continue
                if len(buffer) >= target_min:
                    idx, score = get_best_split(buffer, len(buffer))
                    acceptable_score = 2 if is_first else 3
                    if idx >= target_min and score >= acceptable_score:
                        chunk = clean_text(buffer[:idx])
                        buffer = buffer[idx:]
                        if chunk:
                            log_chunk(chunk)
                            yield chunk
                        continue
                break
                
    except asyncio.CancelledError:
        feeder_task.cancel()
        raise
    except Exception:
        feeder_task.cancel()
        raise
        
    chunk = clean_text(buffer)
    if chunk:
        log_chunk(chunk)
        yield chunk
