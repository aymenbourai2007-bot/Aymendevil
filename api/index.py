import os
import json
from flask import Flask, request
import requests

# --- الإعدادات الأساسية ---
# توكن التحقق (Webhook Verification Token)
VERIFY_TOKEN = "boykta 2023" 
# رمز الوصول للصفحة (يجب الحصول عليه من فيسبوك)
# يفضل بشدة وضعه كمتغير بيئة (Environment Variable) في Vercel
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN', 'YOUR_PAGE_ACCESS_TOKEN_HERE') 

# عناوين الـ API
AI_API_URL = "https://vetrex.x10.mx/api/gpt4.php"
IMAGE_API_URL = "https://sii3.top/api/imagen-3.php"

# يتم استخدام Flask لإنشاء خادم الويب على Vercel
app = Flask(__name__)

# ------------------------------------
# دالة إرسال رسالة نصية أو سريعة الرد
# ------------------------------------
def send_message(recipient_id, message_text, quick_replies=None):
    """إرسال رسالة نصية مع خيار إضافة أزرار الرد السريع."""
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    # إضافة أزرار الرد السريع (Quick Replies)
    if quick_replies:
        data["message"]["quick_replies"] = quick_replies

    response = requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params=params,
        headers=headers,
        data=json.dumps(data)
    )
    return response

# ------------------------------------
# دالة إرسال صورة (من URL)
# ------------------------------------
def send_image(recipient_id, image_url):
    """إرسال صورة باستخدام رابط URL إلى المستخدم."""
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            # استخدام Attachment Type: image لإرسال الصورة، وهو مدعوم في Messenger و Lite
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        }
    }
    
    response = requests.post(
        "https://graph.facebook.com/v18.0/me/messages",
        params=params,
        headers=headers,
        data=json.dumps(data)
    )
    return response

# ------------------------------------
# دالة استدعاء API الذكاء الاصطناعي
# ------------------------------------
def get_ai_response(text):
    """استدعاء API الذكاء الاصطناعي والحصول على الإجابة (answer) فقط."""
    try:
        response = requests.get(f"{AI_API_URL}?text={text}")
        response.raise_for_status()
        
        data = response.json()
        
        # استخلاص الجواب من حقل "answer" كما طلبت
        answer = data.get("answer", "عذراً، لم أتمكن من الحصول على جواب من الذكاء الاصطناعي.")
        return answer
    except Exception as e:
        print(f"Error calling AI API: {e}")
        return "حدث خطأ في الاتصال بخدمة الذكاء الاصطناعي."

# ------------------------------------
# دالة استدعاء API إنشاء الصور
# ------------------------------------
def get_image_url(prompt):
    """استدعاء API إنشاء الصور والحصول على رابط الصورة (image)."""
    try:
        # استخدام التنسيق المطلوب
        response = requests.get(f"{IMAGE_API_URL}?text={prompt}&aspect_ratio=1:1&style=Auto")
        response.raise_for_status()
        
        res_data = response.json()
        
        # استخلاص رابط الصورة من حقل "image"
        image_url = res_data.get("image")
        
        return image_url
    except Exception as e:
        print(f"Error calling Image API: {e}")
        return None

# ------------------------------------
# مسار الـ Webhook (لاستقبال طلبات فيسبوك)
# ------------------------------------
@app.route('/', methods=['GET', 'POST'])
def webhook():
    """معالجة طلبات GET (للتأكيد) و POST (للرسائل)"""
    if request.method == 'GET':
        # --- التحقق من الـ Webhook (GET) ---
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode and token and mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook Verified!")
            return challenge, 200
        else:
            return 'Verification token mismatch', 403

    elif request.method == 'POST':
        # --- معالجة الرسائل الواردة (POST) ---
        data = request.get_json()

        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    sender_id = messaging_event["sender"]["id"]

                    if messaging_event.get("message"):
                        message = messaging_event["message"]
                        message_text = message.get("text", "").strip()
                        lower_text = message_text.lower()
                        
                        # --- منطق إنشاء الصور (الخطوة 2: استقبال الوصف) ---
                        # يتم التحقق هنا مما إذا كانت الرسالة الحالية هي رد على زر "إنشاء صورة"
                        if message.get("quick_reply"):
                            payload = message["quick_reply"]["payload"]
                            if payload == "IMAGE_MODE_PROMPT":
                                # الرسالة الحالية هي وصف الصورة
                                prompt = message_text
                                send_message(sender_id, f"جارٍ إنشاء الصورة لوصف: {prompt}...")
                                image_url = get_image_url(prompt)
                                
                                if image_url:
                                    # إرسال الصورة مباشرة للمستخدم
                                    send_image(sender_id, image_url)
                                else:
                                    send_message(sender_id, "عذراً، لم أتمكن من إنشاء الصورة الآن. يرجى تجربة وصف آخر.")
                                continue 

                        # --- الردود الخاصة (المطور) ---
                        if any(phrase in lower_text for phrase in ["مطورك", "من أنشئك", "من أنتجك", "من صممك"]):
                            response_text = "**aymen bourai** هو مطوري، وأنا مساعد له ومتاح لخدمتك."
                            send_message(sender_id, response_text)
                            continue 
                        
                        # --- الرد الأساسي (الذكاء الاصطناعي) ---
                        if message_text:
                            # 1. الحصول على الرد من API
                            ai_answer = get_ai_response(message_text)
                            
                            # 2. إعداد زر "إنشاء صور" كـ Quick Reply (الخطوة 1: ظهور الزر)
                            quick_replies = [
                                {
                                    "content_type": "text",
                                    "title": "🖼️ إنشاء صورة بالذكاء الاصطناعي",
                                    "payload": "IMAGE_MODE_PROMPT" # Payload للإشارة إلى أن الرسالة القادمة هي وصف صورة
                                }
                            ]
                            
                            # 3. إرسال الرد مع الزر
                            send_message(sender_id, ai_answer, quick_replies=quick_replies)

        return 'EVENT_RECEIVED', 200

# ------------------------------------
# تشغيل التطبيق (نقطة الدخول في Vercel)
# ------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
