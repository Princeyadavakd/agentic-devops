from dotenv import load_dotenv; load_dotenv()
import os
from google import genai
c = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
m = os.getenv("GEMINI_MODEL")
print("model in .env:", m)
try:
    r = c.models.generate_content(model=m, contents="Say OK")
    print("SUCCESS:", r.text)
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:400])
    try:
        print("flash models:", [x.name for x in c.models.list() if "flash" in x.name][:15])
    except Exception as e2:
        print("list failed:", str(e2)[:200])
