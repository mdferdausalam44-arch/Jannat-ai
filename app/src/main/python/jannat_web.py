import os
import time
import threading
import json
import urllib.parse
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, render_template_string, send_from_directory
import bot_memory as brain

app = Flask(__name__, static_folder=None)
SESSION_PATH = os.path.expanduser("~/.jannat_firebase_session.json")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

PAGE = r"""
<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jannat AI</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#10131c;color:#f7f4ff;font-family:Arial,sans-serif}
header{padding:18px;text-align:center;background:#191d2a;border-bottom:1px solid #303548}
header h2{margin:0;color:#e7c7ff}
header p{margin:7px 0 0;color:#b8b6c9;font-size:13px}
#chat{max-width:700px;margin:auto;padding:18px 14px 180px}
.msg{padding:12px 15px;margin:12px 0;border-radius:17px;max-width:88%;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}
.me{background:#37365b;margin-left:auto}
.jannat{background:#252a3b;margin-right:auto}
#status{text-align:center;color:#c8b1e8;font-size:13px;margin:12px}
footer{position:fixed;bottom:0;left:0;right:0;background:#191d2a;padding:14px;border-top:1px solid #303548}
#controls{max-width:700px;margin:auto;display:flex;gap:9px;align-items:center}
button{border:0;border-radius:16px;padding:13px 17px;font-size:16px;cursor:pointer}
#mic{background:#b985e8;color:#20132b;font-size:24px;min-width:58px}
#send{background:#6f65b7;color:white}
#text{flex:1;min-width:0;padding:13px;border-radius:14px;border:1px solid #45475e;background:#10131c;color:white;font-size:16px}
.small{text-align:center;color:#aaaabd;font-size:12px;margin-top:10px}
</style>
</head>
<body>
<header>
<h2>🌸 Jannat AI</h2>
<p>তোমার সঙ্গে বাংলায় কথা বলার ছোট্ট সঙ্গী</p>
</header>
<div id="chat">
<div class="msg jannat">আসসালামু আলাইকুম! ❤️ আমি জান্নাত। আমার সঙ্গে কথা বলো।</div>
</div>
<div id="status">তুমি চাইলে লিখতে পারো অথবা 🎙️ বোতামে চাপ দিতে পারো।</div>
<footer>
<div id="controls">
<button id="mic" title="কথা বলো">🎙️</button>
<input id="text" placeholder="এখানে লিখো..." autocomplete="off">
<button id="send">পাঠাও</button>
</div>
<div class="small">ভয়েসের সুবিধা ফোনের ব্রাউজারের সমর্থনের ওপর নির্ভর করে।</div>
</footer>
<script>
const chat=document.getElementById('chat');
const input=document.getElementById('text');
const statusBox=document.getElementById('status');
const mic=document.getElementById('mic');
let busy=false;

function bubble(text,who){
  const el=document.createElement('div');
  el.className='msg '+who;
  el.textContent=text;
  chat.appendChild(el);
  window.scrollTo(0,document.body.scrollHeight);
  return el;
}
function speak(text){
  if(!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(text);
  u.lang='bn-BD';
  u.rate=0.9;
  u.pitch=1.08;
  const voices=speechSynthesis.getVoices();
  const voice=voices.find(v=>/^bn(-|_)/i.test(v.lang));
  if(voice) u.voice=voice;
  speechSynthesis.speak(u);
}
async function sendMessage(text){
  text=(text||'').trim();
  if(!text||busy) return;
  busy=true;
  input.value='';
  bubble(text,'me');
  const waiting=bubble('একটু অপেক্ষা করো, উত্তর তৈরি করছি…','jannat');
  statusBox.textContent='জান্নাত ভাবছে…';
  try{
    const res=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text})
    });
    const data=await res.json();
    waiting.textContent=data.answer||data.error||'উত্তর পাওয়া যায়নি।';
    statusBox.textContent='জান্নাত উত্তর দিয়েছে ❤️';
    chat.scrollTop=chat.scrollHeight;
    requestAnimationFrame(()=>{
      if(data.answer){
        try { speak(data.answer); }
        catch(e){ console.log('Voice error:',e); }
      }
    });
  }catch(e){
    waiting.textContent='সংযোগে সমস্যা হয়েছে। Termux-এ Jannat চালু আছে কি না দেখো।';
    statusBox.textContent='সংযোগে সমস্যা';
  }finally{busy=false;}
}
document.getElementById('send').onclick=()=>sendMessage(input.value);
input.addEventListener('keydown',e=>{if(e.key==='Enter')sendMessage(input.value)});

const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SpeechRecognition){
  const recognition=new SpeechRecognition();
  recognition.lang='bn-BD';
  recognition.interimResults=false;
  recognition.maxAlternatives=1;
  recognition.onstart=()=>{mic.textContent='⏹️';statusBox.textContent='শুনছি… এখন কথা বলো';};
  recognition.onresult=e=>{
    const text=e.results[0][0].transcript;
    input.value=text;
    sendMessage(text);
  };
  recognition.onerror=e=>{
    statusBox.textContent='কথা শোনা যায়নি: '+e.error+'. চাইলে লিখে পাঠাও।';
  };
  recognition.onend=()=>{mic.textContent='🎙️';};
  mic.onclick=()=>{
    try{recognition.start();}
    catch(e){statusBox.textContent='একটু অপেক্ষা করে আবার মাইক্রোফোন চাপ দাও।';}
  };
}else{
  mic.onclick=()=>{
    statusBox.textContent='এই ব্রাউজারে ভয়েস ইনপুট নেই। Chrome-এ চেষ্টা করো অথবা লিখে পাঠাও।';
  };
}
if('speechSynthesis' in window) speechSynthesis.getVoices();
</script>
</body>
</html>
"""

def get_firebase_session():
    with open(SESSION_PATH, "r") as f:
        saved = json.load(f)

    url = (
        "https://securetoken.googleapis.com/v1/token?key="
        + saved["api_key"]
    )
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": saved["refresh_token"]
    }).encode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode())

    saved["refresh_token"] = result.get(
        "refresh_token", saved["refresh_token"]
    )
    with open(SESSION_PATH, "w") as f:
        json.dump(saved, f)
    os.chmod(SESSION_PATH, 0o600)

    return result["id_token"], saved["localId"]


@app.route("/")
def home():
    return send_from_directory(os.path.expanduser("~/Jannat-ai-github"), "index.html")


@app.route("/static/<path:filename>")
def new_static_files(filename):
    return send_from_directory(os.path.expanduser("~/Jannat-ai-github/static"), filename)


@app.route("/api/chat", methods=["POST"])
def chat():
    message = (request.get_json(silent=True) or {}).get("message", "")
    message = str(message).strip()

    if not message:
        return jsonify(error="আগে কিছু বলো বা লেখো।"), 400

    if not GEMINI_KEY:
        return jsonify(error="GEMINI_API_KEY সেট করা নেই।"), 500

    try:
        t0 = time.perf_counter()
        token, user_id = get_firebase_session()
        t1 = time.perf_counter()
        memories = brain.read_memories(token, user_id)
        t2 = time.perf_counter()
        history = brain.read_history(token, user_id)
        t3 = time.perf_counter()
        related = brain.search_history(token, user_id, message)
        t4 = time.perf_counter()

        answer = brain.ask_gemini(
            GEMINI_KEY, memories, history, message, related
        )
        t5 = time.perf_counter()

        def save_in_background():
            started = time.perf_counter()
            try:
                brain.save_conversation(token, user_id, message, answer)

                memory_triggers = (
                    "মনে রাখ", "মনে রেখো", "মনে রাখবে",
                    "আমার নাম", "আমার পছন্দ", "আমার লক্ষ্য",
                    "আমি থাকি", "আমি চাই তুমি", "ভবিষ্যতে"
                )
                if any(trigger in message for trigger in memory_triggers):
                    memory = brain.extract_memory(GEMINI_KEY, message)
                    if memory and memory not in memories:
                        brain.save_memory(token, user_id, memory)

                print(
                    "BACKGROUND_SAVE_OK {:.2f}s".format(
                        time.perf_counter() - started
                    ),
                    flush=True
                )
            except Exception as save_error:
                print("BACKGROUND_SAVE_ERROR:", repr(save_error), flush=True)

        threading.Thread(target=save_in_background).start()

        print(
            "TIMING session={:.2f}s memories={:.2f}s history={:.2f}s "
            "search={:.2f}s gemini={:.2f}s response_total={:.2f}s".format(
                t1-t0, t2-t1, t3-t2, t4-t3, t5-t4, t5-t0
            ),
            flush=True
        )
        return jsonify(answer=answer)

    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print("HTTP error:", e.code, detail)
        return jsonify(error="সার্ভারে সমস্যা হয়েছে (HTTP {}).".format(e.code)), 500
    except Exception as e:
        import traceback
        print("Jannat error:", repr(e), flush=True)
        traceback.print_exc()
        return jsonify(error="সমস্যা হয়েছে। Termux-এর আউটপুট দেখে নাও।"), 500


if __name__ == "__main__":
    if not os.path.exists(SESSION_PATH):
        print("Firebase session পাওয়া যায়নি। আগে bot_memory.py চালিয়ে লগইন করো।")
    elif not GEMINI_KEY:
        print("GEMINI_API_KEY পাওয়া যায়নি। আগে সেট করো।")
    else:
        print("Jannat interface চালু হচ্ছে…")
        print("ফোনের Chrome-এ http://127.0.0.1:5001 খোলো।")
        app.run(host="127.0.0.1", port=5001, debug=False)
