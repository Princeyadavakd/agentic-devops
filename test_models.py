from dotenv import load_dotenv; load_dotenv()
import os, time
from google import genai
from google.genai import types
c = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=25000))
for m in ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash"]:
    t = time.time()
    try:
        r = c.models.generate_content(model=m, contents="Say OK")
        print(f"{m:26s} OK   {time.time()-t:4.1f}s  {r.text.strip()[:20]}")
    except Exception as e:
        print(f"{m:26s} FAIL {time.time()-t:4.1f}s  {type(e).__name__} {str(e)[:60]}")
