import os
from google import genai
client = genai.Client()
for m in client.models.list():
    if "embedContent" in m.supported_generation_methods:
        print(m.name)
