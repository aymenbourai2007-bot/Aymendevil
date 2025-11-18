# api/index.py
from flask import Flask, request
import os
import requests
import logging
import urllib.parse

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# إعدادات البيئة - ضع PAGE_ACCESS_TOKEN في متغيرات بيئة Vercel
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta2023")
FB_SEND_URL = "https://graph.facebook.com/v16.0/me/messages"

DEVELOPER_REPLY = (
    "نعم aymen bourai هو مطوري. "
    "شاب مبرمج بعمر 18 سنة، متخصص في تطوير البوتات والحلول السيبرانية، "
    "يمتلك خبرة قوية في Python وHTML. يعمل بشكل مستقل ويتميز بدقة عالية وقدرة على ابتكار حلول ذكية وسريعة. "
    "يحب بناء أنظمة فعّالة وأتمتة المهام بابتكار، ويحرص دائمًا على تطوير مهاراته ومواكبة تقنيات البرمجة الحديثة."
)

# دالة لإرسال نص عبر Send API (بدون أزرار)
def send_text(recipient_id: str, text: str) -> bool:
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
        logging.info("Sent message: %s", resp.text)
        return True
    except Exception:
        logging.exception("Failed sending message")
        return False

def extract_first_sentence(text: str) -> str:
    """ارجع الجملة الأولى من النص (تدعم العربية والإنجليزية)"""
    if not isinstance(text, str) or not text.strip():
        return ""
    s = " ".join(text.splitlines()).strip()
    # فواصل ممكنة
    seps = [".", "؟", "!", "?", "۔"]
    # افصل على أي فاصل موجود أولًا بترتيب
    min_idx = None
    chosen_sep = None
    for sep in seps:
        idx = s.find(sep)
        if idx != -1:
            if min_idx is None or idx < min_idx:
                min_idx = idx
                chosen_sep = sep
    if min_idx is not None:
        first = s[:min_idx+1].strip()
        return first
    # إن لم نجد فاصل، اقتطع أول 200 حرفاً وكمل بثلاث نقاط إن كان أطول
    return (s[:200].rstrip() + ("..." if len(s) > 200 else "")).strip()

def extract_from_api_json(j):
    """ابحث عن حقل answer أو حقول شائعة أخرى داخل JSON"""
    if isinstance(j, dict):
        if "answer" in j and isinstance(j["answer"], str) and j["answer"].strip():
            return j["answer"].strip()
        for key in ("text", "response", "message", "reply", "output"):
            if key in j and isinstance(j[key], str) and j[key].strip():
                return j[key].strip()
        # choices -> first -> text
        if "choices" in j and isinstance(j["choices"], list) and j["choices"]:
            first = j["choices"][0]
            if isinstance(first, dict):
                for k in ("text", "message", "content"):
                    if k in first and isinstance(first[k], str) and first[k].strip():
                        return first[k].strip()
        if "data" in j and isinstance(j["data"], dict):
            for k in ("answer", "text", "message"):
                if k in j["data"] and isinstance(j["data"][k], str) and j["data"][k].strip():
                    return j["data"][k].strip()
    return None

def is_developer_question(text: str) -> bool:
    """تحقق من أسئلة مثل من أنت؟ من مطورك؟ أو اسم aymen bourai"""
    if not text:
        return False
    low = text.lower()
    # تحقق من اسم المطور
    if "aymen bourai" in low or "aymenbourai" in low.replace(" ", ""):
        return True
    # عبارات عربية شائعة
    arabic_queries = ["من أنت", "من أنت؟", "من انت", "من مطورك", "من مطورك؟", "من أنشأك", "من أنشئك", "من صنعك", "من صممك"]
    for q in arabic_queries:
        if q in low:
            return True
    # انجليزي شائع
    eng = ["who are you", "who made you", "who is your developer", "who developed you"]
    for q in eng:
        if q in low:
            return True
    return False

@app.route("/", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    logging.info("Verify request: mode=%s token=%s", mode, token)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/", methods=["POST"])
def webhook():
    body = request.get_json(silent=True)
    logging.info("Webhook body: %s", body)
    if not body:
        return "Bad Request", 400

    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            if not sender_id:
                continue
            message = event.get("message", {})
            text = ""
            if isinstance(message.get("text", ""), str):
                text = message.get("text", "").strip()
            else:
                # لا نتعامل مع وسائط حالياً
                send_text(sender_id, "أتعامل حاليًا مع الرسائل النصية فقط.")
                continue

            if not text:
                send_text(sender_id, "أتعامل حاليًا مع الرسائل النصية فقط.")
                continue

            # حالة المطور أو من أنت
            if is_developer_question(text):
                send_text(sender_id, DEVELOPER_REPLY)
                continue

            # خلاف ذلك استدعاء API الخارجي
            try:
                encoded = urllib.parse.quote_plus(text)
                api_url = f"https://sii3.top/api/openai.php?gpt-5-mini={encoded}"
                logging.info("Calling external AI API: %s", api_url)
                resp = requests.get(api_url, timeout=12)
                resp.raise_for_status()
                reply_candidate = None
                try:
                    data = resp.json()
                    reply_candidate = extract_from_api_json(data)
                except ValueError:
                    logging.warning("External API response is not JSON or could not parse JSON")

                if not reply_candidate:
                    # استخدم النص الخام كرد احتياطي
                    raw = resp.text.strip()
                    if raw:
                        reply_candidate = raw

                if not reply_candidate:
                    final = "عذراً، لم أتمكن من الحصول على رد من خدمة الذكاء الاصطناعي الآن."
                else:
                    final = extract_first_sentence(reply_candidate)
                    if not final:
                        final = "عذراً، لم أستطع استخراج رد مناسب."

                send_text(sender_id, final)
            except Exception:
                logging.exception("Error calling external API or sending message")
                send_text(sender_id, "حدث خطأ أثناء معالجة الطلب.")
    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
