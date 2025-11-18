# api/index.py
from flask import Flask, request
import os
import requests
import logging
import urllib.parse

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# environment variables (set these in Vercel project settings)
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta2023")
FB_SEND_URL = "https://graph.facebook.com/v16.0/me/messages"

DEVELOPER_REPLY = (
    "نعم aymen bourai هو مطوري. "
    "شاب مبرمج بعمر 18 سنة، متخصص في تطوير البوتات والحلول السيبرانية، "
    "يمتلك خبرة قوية في Python وHTML. يعمل بشكل مستقل ويتميز بدقة عالية وقدرة على ابتكار حلول ذكية وسريعة. "
    "يحب بناء أنظمة فعّالة وأتمتة المهام بابتكار، ويحرص دائمًا على تطوير مهاراته ومواكبة تقنيات البرمجة الحديثة."
)

def send_text(recipient_id: str, text: str) -> bool:
    """إرسال نص بسيط عبر Send API"""
    if not PAGE_ACCESS_TOKEN:
        logging.error("PAGE_ACCESS_TOKEN is not set")
        return False
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    try:
        resp = requests.post(FB_SEND_URL, params=params, json=payload, timeout=10)
        resp.raise_for_status()
        logging.info("Message sent: %s", resp.text)
        return True
    except Exception as e:
        logging.exception("Failed to send message")
        return False

def extract_single_sentence_from_text(s: str) -> str:
    """خذ جملة مفيدة واحدة - الجملة الأولى من النص"""
    if not s or not isinstance(s, str):
        return ""
    # استبدال سطور جديدة بمسافة
    s = " ".join(s.splitlines()).strip()
    # فصل على علامات النهاية . ? ! ثم أخذ الجزء الأول الذي يحتوي شيء
    for sep in (".", "؟", "!", "?"):
        if sep in s:
            parts = [p.strip() for p in s.split(sep) if p.strip()]
            if parts:
                first = parts[0]
                # إعادة إضافة نقطه مناسبة بناءً على الفاصل الأصلي
                return first + (sep if sep in ".؟!?" else ".")
    # إن لم نُجد فواصل، اقتطع حتى 200 حرف كحد أقصى
    return s[:200].rstrip() + ("..." if len(s) > 200 else "")

def extract_text_from_api_json(j):
    """حاول استخراج نص مفيد من JSON (مفتاح answer أولاً ثم حقول شائعة)"""
    if isinstance(j, dict):
        # مفتاح answer له الأولوية
        if "answer" in j and isinstance(j["answer"], str) and j["answer"].strip():
            return j["answer"].strip()
        # حقول شائعة أخرى
        for key in ("text", "response", "message", "reply", "output"):
            if key in j and isinstance(j[key], str) and j[key].strip():
                return j[key].strip()
        # choices -> أول عنصر -> text أو message
        if "choices" in j and isinstance(j["choices"], list) and j["choices"]:
            first = j["choices"][0]
            if isinstance(first, dict):
                for k in ("text", "message", "content"):
                    if k in first and isinstance(first[k], str) and first[k].strip():
                        return first[k].strip()
        # data subobject
        if "data" in j and isinstance(j["data"], dict):
            for k in ("answer", "text", "message"):
                if k in j["data"] and isinstance(j["data"][k], str) and j["data"][k].strip():
                    return j["data"][k].strip()
    return None

@app.route("/", methods=["GET"])
def verify():
    """Webhook verification endpoint used by Facebook"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    logging.info("Verify request: mode=%s token=%s", mode, token)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/", methods=["POST"])
def webhook():
    """استقبال أحداث من فيسبوك"""
    body = request.get_json(silent=True)
    logging.info("Incoming body: %s", body)
    if body is None:
        return "Bad Request", 400

    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            if not sender_id:
                continue

            message = event.get("message")
            if not message:
                continue

            user_text = message.get("text", "").strip() if isinstance(message.get("text", ""), str) else ""
            if not user_text:
                # لا نتعامل مع أنواع الوسائط هنا
                send_text(sender_id, "أتعامل حاليًا مع الرسائل النصية فقط.")
                continue

            lower = user_text.lower()
            # شرط المطور
            if "aymen bourai" in lower or "aymenbourai" in lower.replace(" ", ""):
                send_text(sender_id, DEVELOPER_REPLY)
                continue

            # خلاف ذلك: استدعاء الـ API الخارجي
            try:
                encoded = urllib.parse.quote_plus(user_text)
                api_url = f"https://sii3.top/api/openai.php?gpt-5-mini={encoded}"
                logging.info("Calling AI API: %s", api_url)
                resp = requests.get(api_url, timeout=12)
                resp.raise_for_status()
                reply_text = None
                # حاول الحصول على JSON
                try:
                    data = resp.json()
                    reply_text = extract_text_from_api_json(data)
                except ValueError:
                    logging.warning("Response is not JSON, using raw text")

                if not reply_text:
                    # إن لم نجد نصًا في JSON نستخدم النص الخام (مقتطع)
                    raw = resp.text.strip()
                    if raw:
                        # لو يبدو كـ JSON ولكن بدون الحقول المتوقعة حاول تفكيك
                        reply_text = raw
                    else:
                        reply_text = ""

                # تأكد أن الرد عبارة عن جملة مفيدة واحدة
                final = extract_single_sentence_from_text(reply_text)
                if not final:
                    final = "عذراً، لا أستطيع الحصول على رد مناسب الآن."

                send_text(sender_id, final)
            except Exception as e:
                logging.exception("Error when calling external API or sending")
                send_text(sender_id, "حدث خطأ أثناء معالجة الطلب.")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    # للتشغيل المحلي فقط
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
