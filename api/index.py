from flask import Flask, request, Response
import requests

app = Flask(name)

# رابط استضافتك الأصلية (التي لا تدعم HTTPS)
# هذا هو الرابط الذي سيحول له Vercel الطلبات
TARGET_SERVER_URL = "http://noel.hidencloud.com:25151/webhook"

@app.route('/webhook', methods=['GET', 'POST'])
def proxy_webhook():
    try:
        # الحالة الأولى: التحقق (Verification) - طلب GET
        if request.method == 'GET':
            # نأخذ البارامترات التي أرسلها فيسبوك (hub.verify_token, hub.challenge)
            params = request.args
            
            # نرسلها كما هي للسيرفر الأصلي
            resp = requests.get(TARGET_SERVER_URL, params=params, timeout=10)
            
            # نعيد إجابة السيرفر الأصلي إلى فيسبوك
            return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

        # الحالة الثانية: استلام الرسائل (Messages) - طلب POST
        elif request.method == 'POST':
            # نأخذ البيانات (JSON)
            json_data = request.get_json()
            
            # نمررها للسيرفر الأصلي
            resp = requests.post(TARGET_SERVER_URL, json=json_data, timeout=10)
            
            # نعيد إجابة السيرفر لفيسبوك
            return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

    except requests.exceptions.ConnectionError:
        return "❌ فشل الاتصال بالسيرفر الأصلي (تأكد أن الاستضافة تعمل)", 502
    except Exception as e:
        return f"❌ حدث خطأ في الوسيط: {str(e)}", 500

@app.route('/', methods=['GET'])
def home():
    return "✅ وسيط Vercel يعمل بنجاح! ويوجه الطلبات إلى noel.hidencloud.com", 200

# هذا السطر ضروري لـ Vercel
if name == 'main':
    app.run()
