// JANNAT AI - Gemini Voice Chat

const micButton = document.querySelector(".mic");
const messageBox = document.querySelector(".message");

let busy = false;

const chatBox = document.createElement("div");
chatBox.style.cssText =
  "width:100%;max-width:500px;margin-top:20px;max-height:220px;overflow-y:auto;text-align:left;";
messageBox.after(chatBox);

function addMessage(text, who) {
  const item = document.createElement("div");
  item.textContent = (who === "me" ? "তুমি: " : "জান্নাত: ") + text;
  item.style.cssText =
    "padding:10px;margin:8px 0;border-radius:12px;background:" +
    (who === "me" ? "#12343b" : "#10252e") +
    ";color:#d9fffa;line-height:1.6;overflow-wrap:anywhere;";
  chatBox.appendChild(item);
  chatBox.scrollTop = chatBox.scrollHeight;
  return item;
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;

  const cleanText = text.replace(/\p{Extended_Pictographic}/gu, "").trim();
  if (!cleanText) return;

  speechSynthesis.cancel();

  const voiceText = new SpeechSynthesisUtterance(cleanText);
  voiceText.lang = "bn-BD";
  voiceText.rate = 0.9;
  voiceText.pitch = 1.1;

  const voices = speechSynthesis.getVoices();
  const bengaliVoice = voices.find(v => /^bn(-|_)/i.test(v.lang));
  if (bengaliVoice) voiceText.voice = bengaliVoice;

  speechSynthesis.speak(voiceText);
}

async function sendToJannat(text) {
  if (busy || !text.trim()) return;

  busy = true;
  addMessage(text, "me");
  messageBox.textContent = "জান্নাত তোমার কথা শুনেছে, উত্তর তৈরি করছে…";

  const waiting = addMessage("একটু অপেক্ষা করো…", "jannat");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "সার্ভারে সমস্যা হয়েছে।");
    }

    waiting.textContent = "জান্নাত: " + data.answer;
    messageBox.textContent = "জান্নাত তোমাকে উত্তর দিয়েছে ❤️";
    speak(data.answer);

  } catch (error) {
    waiting.textContent = "সমস্যা: " + error.message;
    messageBox.textContent = "আবার চেষ্টা করো।";
  } finally {
    busy = false;
  }
}

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition) {
  const recognition = new SpeechRecognition();
  recognition.lang = "bn-BD";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    micButton.textContent = "🔴";
    messageBox.textContent = "বলতে থাকো, আমি শুনছি…";
  };

  recognition.onresult = event => {
    const spokenText = event.results[0][0].transcript;
    sendToJannat(spokenText);
  };

  recognition.onerror = event => {
    messageBox.textContent =
      "মাইক্রোফোনে সমস্যা: " + event.error;
  };

  recognition.onend = () => {
    micButton.textContent = "🎙";
  };

  micButton.addEventListener("click", () => {
    if (busy) return;
    try {
      recognition.start();
    } catch (error) {
      messageBox.textContent = "একটু অপেক্ষা করে আবার চাপ দাও।";
    }
  });

} else {
  micButton.addEventListener("click", () => {
    messageBox.textContent =
      "এই ব্রাউজারে ভয়েস সুবিধা নেই। Chrome ব্যবহার করো।";
  });
}
