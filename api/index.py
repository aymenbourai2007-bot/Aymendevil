# api/index.py
from flask import Flask, request, jsonify
import os
import requests
import urllib.parse
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "boykta2023")
FB_SEND_URL = "https://graph.facebook.com/v16.0/me/messages"

# النص الذي يرد عند السؤال عن المطور (بالضبط كما طلبت)
DEVELOPER_REPLY = (
    "نعم aymen bourai هو مطوري\n"
    "شاب مبرمج بعمر 18 سنة، متخصص في تطوير البوتات والحلول السيبرانية، "
    "يمتلك خبرة قوية في Python وHTML. يعمل بشكل مستقل ويتميز بدقة عالية وقدرة على ابتكار حلول ذكية وسريعة. "
    "يحب بناء أنظمة فعّالة وأتمتة المهام بابتكار، ويحرص دائمًا على تطوير مهاراته ومواكبة تقنيات البرمجة الحديثة."
)

# دالة مساعدة لإرسال رسالة نصية عبر Send API
def send_text_message(recipient_id, text, quick_replies=None):
    if not PAGE_ACCESS_TOKEN:
        logging.error("PAGE_ACCESS_TOKEN not set in environment")
        return False

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }

    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies

    params = {"access_token": PAGE_ACCESS_TOKEN}
    resp = requests.post(FB_SEND_URL, params=params, json=payload, timeout=10)
    if resp.status_code != 200:
        logging.error("Failed to send message: %s %s", resp.status_code, resp.text)
        return False
    return True

# محاولة استخراج الجملة المفيدة من استجابة الـ API
def extract_text_from_api_json(j):
    # بحث عن حقول شائعة
    for key in ("answer", "response", "text", "message", "msg", "reply", "output"):
        if isinstance(j, dict) and key in j and isinstance(j[key], str):
            return j[key].strip()
    # أحيانًا تكون في choices أو data
    if isinstance(j, dict):
        if "choices" in j and isinstance(j["choices"], list) and len(j["choices"])>0:
            first = j["choices"][0]
            if isinstance(first, dict):
                for k in ("text","message","content"):
                    if k in first and isinstance(first[k], str):
                        return first[k].strip()
        if "data" in j and isinstance(j["data"], dict):
            # تفتش داخل data
            for k in ("text","answer","message"):
                if k in j["data"] and isinstance(j["data"][k], str):
                    return j["data"][k].strip()
    # إن لم نجد شيء نعيد تمثيل نصي مصغر
    return None

# GET: التحقق من webhook
@app.route("/", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    logging.info("Webhook verify request: mode=%s token=%s", mode, token)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# POST: استقبال الرسائل
@app.route("/", methods=["POST"])
def webhook():
    body = request.get_json()
    logging.info("Incoming webhook body: %s", body)

    if body is None:
        return "Bad Request - no JSON", 400

    # فيسبوك يضع الأحداث داخل "entry" -> "messaging"
    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            if not sender_id:
                continue

            # رسالة نصية
            message = event.get("message")
            if message:
                # نص المستخدم
                user_text = None
                if "text" in message:
                    user_text = message["text"].strip()
                # quick reply payload
                if "quick_reply" in message and isinstance(message["quick_reply"], dict):
                    qr_payload = message["quick_reply"].get("payload", "")
                    # لو payload = DEVELOPER أو WHOAMI نستخدم نفس المنطق
                    if qr_payload == "WHO_ARE_YOU" or qr_payload == "WHO_IS_DEV":
                        send_text_message(sender_id, DEVELOPER_REPLY)
                        continue

                if user_text:
                    lower = user_text.lower()
                    # شرط خاص: إذا النص يحتوي على "aymen bourai" نرد وصف المطور
                    if "aymen bourai" in lower or "aymenbourai" in lower.replace(" ", ""):
                        send_text_message(sender_id, DEVELOPER_REPLY)
                        continue

                    # خلاف ذلك: نسأل API الخارجي ونأخذ إجابة واحدة مفيدة من JSON
                    try:
                        encoded = urllib.parse.quote_plus(user_text)
                        api_url = f"https://sii3.top/api/openai.php?gpt-5-mini={encoded}"
                        logging.info("Calling AI API: %s", api_url)
                        r = requests.get(api_url, timeout=12)
                        r.raise_for_status()
                        data = None
                        try:
                            data = r.json()
                        except Exception as e:
                            logging.warning("API did not return JSON: %s", e)
                        reply_text = None
                        if isinstance(data, dict):
                            reply_text = extract_text_from_api_json(data)
                        # إذا لم نجد نصًا داخل JSON نجرب استخدام النص الخام للـ response
                        if not reply_text:
                            # حاول استخراج نص بسيط من body إن كان نصيًا
                            text_guess = r.text.strip()
                            # احذف أقواس JSON الطويلة لو كانت
                            if text_guess:
                                # اختصر لو طويل جدًا
                                if len(text_guess) > 1000:
                                    text_guess = text_guess[:1000] + "..."
                                reply_text = text_guess
                        if not reply_text:
                            reply_text = "عذراً، لم أستطع الحصول على رد من خدمة الذكاء الاصطناعي الآن."

                        # أضف أزرار Quick Replies صغيرة لمساعدة المستخدم (يمكن حذفها)
                        quick_replies = [
                            {"content_type": "text", "title": "من أنت؟", "payload": "WHO_ARE_YOU"},
                            {"content_type": "text", "title": "من مطورك؟", "payload": "WHO_IS_DEV"}
                        ]
                        send_text_message(sender_id, reply_text, quick_replies=quick_replies)
                    except Exception as e:
                        logging.exception("Error when calling AI API or sending message")
                        send_text_message(sender_id, "حصل خطأ داخلي أثناء معالجة الرسالة.")
                else:
                    # لا يوجد نص، ربما مرفق - نرد رسالة افتراضية
                    send_text_message(sender_id, "أستقبلت مرفقًا ولكنني أتعامل الآن مع الرسائل النصية فقط.")
    return "EVENT_RECEIVED", 200

# للإختبار المحلي (لن يستخدم في Vercel عادة)
if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
