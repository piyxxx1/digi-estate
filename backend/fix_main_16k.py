import codecs

with codecs.open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'asyncio.create_task(_ensure_greeting_cached("inbound", 8000))\n    asyncio.create_task(_ensure_greeting_cached("outbound", 8000))',
    'asyncio.create_task(_ensure_greeting_cached("inbound", 8000))\n    asyncio.create_task(_ensure_greeting_cached("outbound", 8000))\n    asyncio.create_task(_ensure_greeting_cached("inbound", 16000))\n    asyncio.create_task(_ensure_greeting_cached("outbound", 16000))'
)

with codecs.open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
