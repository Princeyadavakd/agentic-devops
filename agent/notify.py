"""Telegram bot: notifications, Approve/Reject buttons and simple commands.
Uses long polling (getUpdates), so no webhook, tunnel or public server is needed.
Only messages from TELEGRAM_CHAT_ID are accepted.

  python -m agent.notify setup    # prints your chat id (send any message to the bot first)
  python -m agent.notify test     # sends a test message and an approval question
"""
import builtins
import json
import os
import sys
import threading
import time
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Bot:
    def __init__(self, token=None, chat_id=None, api_base=None):
        self.token = token if token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID", ""))
        self.api = (api_base or os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")).rstrip("/")
        self.pending = {}
        self.handlers = {}
        self.offset = 0
        self._thread = None
        self._stop = threading.Event()
        self._ask_lock = threading.Lock()
        self._n = 0

    @property
    def enabled(self):
        return bool(self.token and self.chat_id)

    def _call(self, method, payload=None, timeout=30):
        req = urllib.request.Request(f"{self.api}/bot{self.token}/{method}", data=json.dumps(payload or {}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    def send(self, text, buttons=None):
        if not self.enabled:
            print("[telegram disabled] " + text)
            return None
        payload = {"chat_id": self.chat_id, "text": text[:4000]}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]}
        try:
            return self._call("sendMessage", payload)
        except Exception as e:
            print(f"[telegram] send failed: {e}")

    def ask(self, question, timeout=300):
        """Send Approve / Reject buttons and wait for a tap. Timeout counts as Reject."""
        with self._ask_lock:
            self._n += 1
            qid = f"{int(time.time())}-{self._n}"
            ev = threading.Event()
            self.pending[qid] = {"event": ev, "answer": False}
            self.send(question, [("Approve", f"ok:{qid}"), ("Reject", f"no:{qid}")])
            got = ev.wait(timeout)
            answer = self.pending.pop(qid)["answer"] if got else False
            if not got:
                self.send("Approval timed out: treated as REJECT.")
            return answer

    def on(self, command, fn):
        self.handlers["/" + command.lstrip("/").lower()] = fn

    def start(self):
        if self.enabled and not self._thread:
            self._thread = threading.Thread(target=self._poll, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _poll(self):
        while not self._stop.is_set():
            try:
                res = self._call("getUpdates", {"offset": self.offset, "timeout": 20,
                                                "allowed_updates": ["message", "callback_query"]}, timeout=40)
                for u in res.get("result", []):
                    self.offset = u["update_id"] + 1
                    self._handle(u)
            except Exception:
                time.sleep(3)

    def _handle(self, u):
        cq = u.get("callback_query")
        if cq:
            if str(cq.get("message", {}).get("chat", {}).get("id")) != self.chat_id:
                return
            action, _, qid = (cq.get("data") or "").partition(":")
            try:
                self._call("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Noted"})
            except Exception:
                pass
            p = self.pending.get(qid)
            if p:
                p["answer"] = (action == "ok")
                p["event"].set()
            return
        msg = u.get("message")
        if msg and str(msg.get("chat", {}).get("id")) == self.chat_id:
            text = (msg.get("text") or "").strip()
            if text.startswith("/"):
                cmd, *args = text.split()
                fn = self.handlers.get(cmd.split("@")[0].lower())
                if fn:
                    threading.Thread(target=self._safe, args=(fn, args), daemon=True).start()
                else:
                    self.send("Commands: " + ", ".join(sorted(self.handlers)))

    def _safe(self, fn, args):
        try:
            fn(args)
        except Exception as e:
            self.send(f"Command failed: {type(e).__name__}: {e}")


_bot = None


def get_bot():
    global _bot
    if _bot is None:
        _bot = Bot()
    return _bot


_real_input = builtins.input


def install_input_hook(bot):
    """Route the agents' console approval prompts ('[approval] ... [y/N]:') to Telegram buttons."""
    def hooked(prompt=""):
        if bot.enabled and "[approval]" in str(prompt):
            question = str(prompt).replace("[approval]", "").replace("[y/N]:", "").strip()
            print(f"{prompt}(sent to Telegram, waiting for your tap...)")
            ok = bot.ask("Approval needed: " + question)
            print(f"[approval] Telegram answer: {'APPROVED' if ok else 'REJECTED'}")
            return "y" if ok else "n"
        return _real_input(prompt)
    builtins.input = hooked


def _setup():
    bot = Bot(chat_id="0")
    if not bot.token:
        print("Set TELEGRAM_BOT_TOKEN in .env first."); return
    res = bot._call("getUpdates", {})
    seen = {}
    for u in res.get("result", []):
        m = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
        c = m.get("chat")
        if c:
            seen[c["id"]] = c.get("first_name") or c.get("title") or ""
    if not seen:
        print("No messages found. Open your bot in Telegram, press Start, send 'hi', then run this again.")
    for cid, name in seen.items():
        print(f"chat id: {cid}   ({name})   -> put TELEGRAM_CHAT_ID={cid} in .env")


def _test():
    bot = get_bot()
    if not bot.enabled:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing in .env"); return
    bot.start()
    bot.send("Agentic DevOps bot is connected.")
    print("Waiting for your tap on the Approve/Reject buttons in Telegram ...")
    print("Result:", "APPROVED" if bot.ask("Test approval: tap a button", timeout=120) else "REJECTED / timed out")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"setup": _setup, "test": _test}.get(cmd, lambda: print("usage: python -m agent.notify setup|test"))()
