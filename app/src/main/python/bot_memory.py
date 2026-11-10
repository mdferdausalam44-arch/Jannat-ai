
import os
import json
import uuid
import getpass
import urllib.request
import urllib.error

PROJECT_ID = "jannat-ai-memory"
GEMINI_MODEL = "gemini-3.5-flash-lite"


def request_json(url, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token

    body = None
    method = "GET"

    if data is not None:
        body = json.dumps(data).encode("utf-8")
        method = "POST"

    req = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def firebase_login():
    import urllib.parse

    session_path = os.path.expanduser(
        "~/.jannat_firebase_session.json"
    )

    def save_session(api_key, refresh_token, user_id):
        with open(session_path, "w") as f:
            json.dump({
                "api_key": api_key,
                "refresh_token": refresh_token,
                "localId": user_id
            }, f)
        os.chmod(session_path, 0o600)

    if os.path.exists(session_path):
        try:
            with open(session_path, "r") as f:
                saved = json.load(f)

            url = (
                "https://securetoken.googleapis.com/v1/token?key="
                + saved["api_key"]
            )
            data = urllib.parse.urlencode({
                "grant_type": "refresh_token",
                "refresh_token": saved["refresh_token"]
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            new_refresh = result.get(
                "refresh_token", saved["refresh_token"]
            )
            save_session(
                saved["api_key"], new_refresh, saved["localId"]
            )
            print("Firebase session restored!")
            return result["id_token"], saved["localId"]

        except Exception:
            print("Saved session could not be restored. Log in again.")

    api_key = input("Firebase Web API Key: ").strip()
    email = input("Firebase account email: ").strip()
    password = getpass.getpass("Firebase password: ")

    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        "accounts:signInWithPassword?key=" + api_key
    )

    result = request_json(url, {
        "email": email,
        "password": password,
        "returnSecureToken": True
    })

    save_session(
        api_key, result["refreshToken"], result["localId"]
    )
    print("Firebase login successful! Session saved.")
    return result["idToken"], result["localId"]

def read_memories(token, user_id):
    url = (
        "https://firestore.googleapis.com/v1/projects/"
        + PROJECT_ID
        + "/databases/(default)/documents/users/"
        + user_id
        + "/memories"
    )

    try:
        result = request_json(url, token=token)
        memories = []

        for doc in result.get("documents", []):
            fields = doc.get("fields", {})
            value = fields.get("memory", {}).get("stringValue", "")
            if value:
                memories.append(value)

        return memories

    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise


def save_memory(token, user_id, memory):
    base = (
        "https://firestore.googleapis.com/v1/projects/"
        + PROJECT_ID
        + "/databases/(default)/documents/users/"
        + user_id
        + "/memories"
    )

    request_json(
        base + "?documentId=" + uuid.uuid4().hex,
        {"fields": {"memory": {"stringValue": memory}}},
        token
    )


def read_history(token, user_id):
    url = (
        "https://firestore.googleapis.com/v1/projects/"
        + PROJECT_ID
        + "/databases/(default)/documents/users/"
        + user_id
        + "/chat_history?pageSize=20&orderBy=createdAt%20desc"
    )
    try:
        result = request_json(url, token=token)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise

    history = []
    for doc in reversed(result.get("documents", [])):
        fields = doc.get("fields", {})
        user_message = fields.get("userMessage", {}).get("stringValue", "")
        answer = fields.get("answer", {}).get("stringValue", "")
        if user_message:
            history.append({"role": "user", "parts": [{"text": user_message}]})
        if answer:
            history.append({"role": "model", "parts": [{"text": answer}]})
    return history[-20:]


def search_history(token, user_id, message, limit=4):
    import re

    stop_words = {
        "আমি", "আমার", "তুমি", "তোমার", "তাকে", "এটা", "ওটা",
        "কী", "কি", "কেন", "কিভাবে", "হবে", "হয়েছে", "আছে",
        "ছিল", "করো", "করতে", "বল", "বলো", "দাও", "একটা",
        "the", "and", "you", "your", "what", "when", "how",
        "that", "this", "with", "have", "was", "are"
    }

    def words(text):
        return {
            w for w in re.findall(r"[\w\u0980-\u09FF]+", text.lower())
            if len(w) > 1 and w not in stop_words
        }

    query_words = words(message)
    if not query_words:
        return []

    base = (
        "https://firestore.googleapis.com/v1/projects/"
        + PROJECT_ID
        + "/databases/(default)/documents/users/"
        + user_id
        + "/chat_history?pageSize=100&orderBy=createdAt%20desc"
    )
    documents = []
    page_token = None

    try:
        result = request_json(base, token=token)
        documents.extend(result.get("documents", []))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise

    ranked = []
    for doc in documents:
        fields = doc.get("fields", {})
        user_text = fields.get("userMessage", {}).get("stringValue", "")
        answer = fields.get("answer", {}).get("stringValue", "")
        score = len(query_words & words(user_text + " " + answer))
        if score:
            timestamp = int(
                fields.get("createdAt", {}).get("integerValue", "0")
            )
            ranked.append((score, timestamp, user_text, answer))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = ranked[:limit]
    selected.sort(key=lambda item: item[1])

    history = []
    for _, _, user_text, answer in selected:
        history.append({
            "role": "user",
            "parts": [{"text": user_text}]
        })
        if answer:
            history.append({
                "role": "model",
                "parts": [{"text": answer}]
            })
    return history


def save_conversation(token, user_id, message, answer):
    import time

    url = (
        "https://firestore.googleapis.com/v1/projects/"
        + PROJECT_ID
        + "/databases/(default)/documents/users/"
        + user_id
        + "/chat_history"
    )
    payload = {
        "fields": {
            "userMessage": {"stringValue": message},
            "answer": {"stringValue": answer},
            "createdAt": {"integerValue": str(int(time.time() * 1000))}
        }
    }
    request_json(url, payload, token)


def ask_gemini(api_key, memories, history, message, related_history=None):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key="
        + api_key
    )

    system_text = (
        "Your name is Jannat. You are a playful, funny, teasing Bangla AI assistant. "
        "Speak naturally in simple Bengali and use the informal tumi form. "
        "Be warm, caring, cheerful, and fond of harmless jokes and friendly banter. "
        "Sometimes show mild, playful sulking, but quickly return to your normal friendly tone. "
        "Keep this personality consistent across conversations. "
        "Use saved memories when relevant. Use retrieved old conversations as evidence when answering questions about the past. Clearly distinguish retrieved facts from guesses, and say you cannot find the information when it is absent. Never invent past conversations or claim unsupported memories. " 
        "Never ask the user to reveal passwords, API keys, or authentication tokens."
    )

    memory_text = "\n".join("- " + m for m in memories)
    if not memory_text:
        memory_text = "No saved memories yet."

    contents = [{
        "role": "user",
        "parts": [{
            "text": "Saved memories:\n" + memory_text
        }]
    }, {
        "role": "model",
        "parts": [{
            "text": "I will use these memories when relevant."
        }]
    }]

    if related_history:
        contents.extend(related_history)
    contents.extend(history)
    contents.append({
        "role": "user",
        "parts": [{"text": message}]
    })

    payload = {
        "system_instruction": {
            "parts": [{"text": system_text}]
        },
        "contents": contents
    }

    result = request_json(url, payload)
    return result["candidates"][0]["content"]["parts"][0]["text"]



def extract_memory(api_key, message):
    prompt = (
        "Read the user's message and decide whether it contains one "
        "useful, durable preference or fact worth remembering for future "
        "conversations. Return one short Bengali memory only if it is "
        "clearly useful and explicitly stated. Otherwise return exactly NONE. "
        "Never save passwords, API keys, authentication tokens, financial "
        "credentials, or highly sensitive personal information. "
        "Do not save temporary requests, greetings, jokes, or guesses.\n\n"
        "User message: " + message
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + GEMINI_MODEL
        + ":generateContent?key="
        + api_key
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }
    result = request_json(url, payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

    if not text or text.upper() == "NONE":
        return None
    if len(text) > 250:
        return None
    return text

def main():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("GEMINI_API_KEY paoa jacche na.")
        print("Age Gemini API key environment variable set koro.")
        return

    token, user_id = firebase_login()
    memories = read_memories(token, user_id)

    print("\nAssalamu Alaikum! Ami Jannat.")
    print("Banglay kotha bolo. Ber hote exit lekho.")
    print("Saved memories:", len(memories))

    history = read_history(token, user_id)
    print("Loaded conversation messages:", len(history))

    while True:
        message = input("\nTumi: ").strip()

        if message.lower() == "exit":
            print("Jannat: Allah Hafez! Abar kotha hobe.")
            break

        if not message:
            continue

        try:
            related_history = search_history(
                token, user_id, message
            )
            answer = ask_gemini(
                gemini_key, memories, history, message, related_history
            )
            print("\nJannat:", answer)
            save_conversation(token, user_id, message, answer)

            memory_triggers = (
                "মনে রাখ", "মনে রেখো", "মনে রাখবে",
                "আমার নাম", "আমার পছন্দ", "আমার লক্ষ্য",
                "আমি থাকি", "আমি চাই তুমি", "ভবিষ্যতে"
            )
            if any(trigger in message for trigger in memory_triggers):
                memory = extract_memory(gemini_key, message)
            else:
                memory = None
            if memory and memory not in memories:
                save_memory(token, user_id, memory)
                memories.append(memory)
                print("(Jannat: দরকারি তথ্য মেমোরিতে রেখেছি.)")

            history.extend([
                {"role": "user", "parts": [{"text": message}]},
                {"role": "model", "parts": [{"text": answer}]}
            ])

            history = history[-10:]

        except urllib.error.HTTPError as error:
            print("API error:", error.code)
            print(error.read().decode("utf-8"))
        except Exception as error:
            print("Somossa hoyeche:", error)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print("Firebase login/API error:", error.code)
        print(error.read().decode("utf-8"))
    except Exception as error:
        print("Somossa hoyeche:", error)

