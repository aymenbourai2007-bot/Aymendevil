from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

# رابط API الذكاء الاصطناعي
AI_API_URL = "https://sii3.top/api/grok4.php?text="

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # التحقق من webhook
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if verify_token == 'boykta2023':
            return challenge
        else:
            return 'Verification token mismatch', 403
    
    elif request.method == 'POST':
        data = request.get_json()
        
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    if messaging_event.get('message'):
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event['message'].get('text', '')
                        
                        # معالجة الرسالة
                        response_text = process_message(message_text)
                        
                        # إرسال الرد
                        send_message(sender_id, response_text)
        
        return 'OK', 200

def process_message(message_text):
    message_text_lower = message_text.lower().strip()
    
    # الرد على الأسئلة عن المطور
    developer_keywords = ['مطورك', 'أنشئك', 'أنتجك', 'صممك', 'من صنعك', 'من أنشأك', 'aymen bourai']
    
    if any(keyword in message_text_lower for keyword in developer_keywords) or 'aymen bourai' in message_text_lower:
        return "نعم Aymen Bouraoui هو مطوري. شاب مبرمج بعمر 18 سنة، متخصص في تطوير البوتات والحلول السيبرانية، يمتلك خبرة قوية في Python وHTML. يعمل بشكل مستقل ويتميز بدقة عالية وقدرة على ابتكار حلول ذكية وسريعة. يحب بناء أنظمة فعّالة وأتمتة المهام بابتكار، ويحرص دائمًا على تطوير مهاراته ومواكبة تقنيات البرمجة الحديثة."
    
    # استخدام API الذكاء الاصطناعي للأسئلة الأخرى
    try:
        response = requests.get(f"{AI_API_URL}{message_text}")
        if response.status_code == 200:
            ai_data = response.json()
            # استخراج الإجابة من JSON
            answer = ai_data.get('answer', ai_data.get('response', 'لم أتمكن من معالجة سؤالك.'))
            return answer
        else:
            return "عذرًا، حدث خطأ في معالجة طلبك."
    except Exception as e:
        return "عذرًا، حدث خطأ في الاتصال بالذكاء الاصطناعي."

def send_message(recipient_id, message_text):
    page_access_token = os.environ.get('PAGE_ACCESS_TOKEN')
    
    if not page_access_token:
        print("Warning: PAGE_ACCESS_TOKEN not set")
        return
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={page_access_token}"
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code != 200:
            print(f"Error sending message: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception in send_message: {e}")

@app.route('/')
def home():
    return "Facebook Bot is running!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
