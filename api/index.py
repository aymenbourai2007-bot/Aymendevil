import os
import json
import urllib.parse
from flask import Flask, request
import requests

# --- الإعدادات الأساسية ---
# توكن التحقق (Webhook Verification Token)
VERIFY_TOKEN = "boykta 2023" 
# رمز الوصول للصفحة (يجب الحصول عليه من فيسبوك)
# هام: يرجى تعيينه كمتغير بيئة (Environment Variable) في Vercel باسم PAGE_ACCESS_TOKEN
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN', 'YOUR_PAGE_ACCESS_TOKEN_HERE') 

# عناوين الـ API
# تم تحديثه إلى API Grok4
AI_API_BASE_URL = "https://sii3.top/api/grok4.php?text="

# الوصف الخاص بالمطور (الرد المخصص)
AYMEN_DESCRIPTION = (
    "نعم، aymen bourai هو مطوري! وهو: "
    "شاب مبرمج بعمر 18 سنة، متخصص في تطوير البوتات والحلول السيبرانية، يمتلك خبرة قوية "
    "في Python وHTML. يعمل بشكل مستقل ويتميز بدقة عالية وقدرة على ابتكار حلول ذكية وسريعة. "
    "يحب بناء أنظمة فعّالة وأتمتة المهام بابتكار، ويحرص دائمًا على تطوير مهاراته ومواكبة تقنيات البرمجة الحديثة."
)

app = Flask(__name__)

# ------------------------------------
# دالة إرسال رسالة نصية
# ------------------------------------
def send_message(recipient_id, message_text):
    """إرسال رسالة نصية إلى المستخدم أو المجموعة."""
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params=params,
        headers=headers,
        data=json.dumps(data)
    )

# ------------------------------------
# دالة استدعاء API الذكاء الاصطناعي
# ------------------------------------
def get_ai_response(text):
    """استدعاء API الذكاء الاصطناعي والحصول على الإجابة (answer) فقط."""
    try:
        # ترميز النص لضمان عمل الروابط مع الأحرف العربية والمسافات
        encoded_text = urllib.parse.quote(text)
        
        # بناء URL وإرسال الطلب
        response = requests.get(f"{AI_API_BASE_URL}{encoded_text}")
        response.raise_for_status() # لرفع استثناء عند وجود أخطاء في الـ API
        
        data = response.json()
        
        # استخلاص الجواب من حقل "answer" كما طلبت
        answer = data.get("answer", "عذراً، لم أتمكن من الحصول على جواب واضح من الذكاء الاصطناعي.")
        return answer
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error calling API: {e}. Check API status.")
        return "حدث خطأ في الاتصال بخدمة الذكاء الاصطناعي، يرجى المحاولة لاحقاً."
    except Exception as e:
        print(f"Error calling AI API: {e}")
        return "حدث خطأ غير متوقع أثناء معالجة الطلب."

# ------------------------------------
# مسار الـ Webhook
# ------------------------------------
@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # --- التحقق من الـ Webhook ---
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode and token and mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Verification token mismatch', 403

    elif request.method == 'POST':
        # --- معالجة الرسائل الواردة ---
        data = request.get_json()

        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    sender_id = messaging_event["sender"]["id"]

                    if messaging_event.get("message") and messaging_event["message"].get("text"):
                        message_text = messaging_event["message"]["text"].strip()
                        lower_text = message_text.lower()
                        
                        # --- الرد الخاص بـ aymen bourai ---
                        # التحقق من ذكر كلمة "aymen bourai" أو السؤال عن المطور
                        if "aymen bourai" in lower_text or \
                           any(phrase in lower_text for phrase in ["مطورك", "من أنشئك", "من أنتجك", "من صممك"]):
                            send_message(sender_id, AYMEN_DESCRIPTION)
                            continue 
                        
                        # --- الرد الأساسي (الذكاء الاصطناعي) ---
                        if message_text:
                            ai_answer = get_ai_response(message_text)
                            send_message(sender_id, ai_answer)

        return 'EVENT_RECEIVED', 200

# ------------------------------------
# تشغيل التطبيق 
# ------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
