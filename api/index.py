import os
import json
from flask import Flask, request
import requests

# --- الإعدادات الأساسية ---
# توكن التحقق (Webhook Verification Token)
VERIFY_TOKEN = "boykta 2023" 
# رمز الوصول للصفحة (يجب الحصول عليه من فيسبوك)
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN', 'YOUR_PAGE_ACCESS_TOKEN_HERE') 

# عناوين الـ API
AI_API_URL = "https://vetrex.x10.mx/api/gpt4.php"
IMAGE_API_URL = "https://sii3.top/api/imagen-3.php"

# قاموس لتخزين حالة المستخدم (لمعرفة متى ينتظر البوت وصف صورة)
# (ملاحظة: هذا يعمل كحل بسيط لـ Vercel، لكن في تطبيقات الإنتاج الكبيرة يفضل استخدام قواعد بيانات أو Redis)
user_states = {} 

app = Flask(__name__)

# ------------------------------------
# دوال إرسال الرسائل والصور
# ------------------------------------
def send_message(recipient_id, message_text, quick_replies=None):
    """إرسال رسالة نصية مع خيار إضافة أزرار الرد السريع."""
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    if quick_replies:
        data["message"]["quick_replies"] = quick_replies

    requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params=params,
        headers=headers,
        data=json.dumps(data)
    )

def send_image(recipient_id, image_url):
    """إرسال رابط الصورة ليعرض كصورة مرئية في المحادثة."""
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        }
    }
    
    requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params=params,
        headers=headers,
        data=json.dumps(data)
    )

# ------------------------------------
# دوال استدعاء API
# ------------------------------------
def get_ai_response(text):
    """استدعاء API الذكاء الاصطناعي والحصول على الإجابة (answer) فقط."""
    try:
        response = requests.get(f"{AI_API_URL}?text={text}")
        response.raise_for_status()
        data = response.json()
        answer = data.get("answer", "عذراً، لم أتمكن من الحصول على جواب واضح.")
        return answer
    except Exception as e:
        print(f"Error calling AI API: {e}")
        return "حدث خطأ في الاتصال بخدمة الذكاء الاصطناعي."

def get_image_url(prompt):
    """استدعاء API إنشاء الصور والحصول على رابط الصورة (image)."""
    try:
        response = requests.get(f"{IMAGE_API_URL}?text={prompt}&aspect_ratio=1:1&style=Auto")
        response.raise_for_status()
        res_data = response.json()
        image_url = res_data.get("image")
        return image_url
    except Exception as e:
        print(f"Error calling Image API: {e}")
        return None

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
        data = request.get_json()

        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    sender_id = messaging_event["sender"]["id"]

                    # ----------------------------------------------------
                    # 1. معالجة الضغط على زر الرد السريع (Quick Reply)
                    # ----------------------------------------------------
                    # هذا الجزء يُعالج الحدث الذي يأتي عندما يضغط المستخدم على الزر
                    if messaging_event.get("message") and messaging_event["message"].get("quick_reply"):
                        payload = messaging_event["message"]["quick_reply"]["payload"]

                        if payload == "IMAGE_MODE_PROMPT":
                            # عند الضغط على زر "إنشاء صورة"
                            
                            # نضع حالة للمستخدم لكي نعرف أن رسالته القادمة هي وصف صورة
                            user_states[sender_id] = "waiting_for_image_prompt"
                            
                            # الرد الذي طلبته بالضبط: "أرسل لي وصف من فضلك"
                            send_message(sender_id, "✨ أرسل لي وصف الصورة التي تريد إنشاءها الآن من فضلك.")
                            continue # التوقف هنا وانتظار الرسالة القادمة (الوصف)

                    # ----------------------------------------------------
                    # 2. معالجة الرسائل النصية العادية
                    # ----------------------------------------------------
                    if messaging_event.get("message") and messaging_event["message"].get("text"):
                        message_text = messaging_event["message"]["text"].strip()
                        lower_text = message_text.lower()
                        
                        # --- معالجة حالة انتظار وصف الصورة ---
                        # يتحقق: هل المستخدم في وضع "انتظار الوصف"؟
                        if user_states.get(sender_id) == "waiting_for_image_prompt":
                            # المستخدم أرسل الوصف الآن
                            prompt = message_text
                            send_message(sender_id, f"جارٍ إنشاء الصورة لوصف: {prompt}...")
                            
                            image_url = get_image_url(prompt)
                            
                            if image_url:
                                # إرسال الصورة للمستخدم (تظهر مرئية في المحادثة)
                                send_image(sender_id, image_url)
                            else:
                                send_message(sender_id, "عذراً، لم أتمكن من إنشاء الصورة الآن. يرجى محاولة وصف آخر.")
                            
                            # إزالة حالة المستخدم بعد الانتهاء
                            if sender_id in user_states:
                                del user_states[sender_id] 
                            continue

                        # --- الردود الخاصة (المطور) ---
                        if any(phrase in lower_text for phrase in ["مطورك", "من أنشئك", "من أنتجك", "من صممك"]):
                            response_text = "**aymen bourai** هو مطوري، وأنا مساعد له ومتاح لخدمتك."
                            send_message(sender_id, response_text)
                            continue 
                        
                        # --- الرد الأساسي (الذكاء الاصطناعي) ---
                        if message_text:
                            ai_answer = get_ai_response(message_text)
                            
                            # إعداد زر "إنشاء صور" كـ Quick Reply
                            quick_replies = [
                                {
                                    "content_type": "text",
                                    "title": "🖼️ إنشاء صورة بالذكاء الاصطناعي",
                                    "payload": "IMAGE_MODE_PROMPT" 
                                }
                            ]
                            
                            send_message(sender_id, ai_answer, quick_replies=quick_replies)

        return 'EVENT_RECEIVED', 200

# ------------------------------------
# تشغيل التطبيق 
# ------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
