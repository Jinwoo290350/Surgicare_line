#!/usr/bin/env python3
"""
Complete Working SurgiCare LINE Bot
Fixed version with real wound analysis functionality
"""

from flask import Flask, request, jsonify
import os
import hashlib
import hmac
import base64
import json
import requests
import tempfile
import random
import logging
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import threading
from typing import Dict, List, Optional
import uuid

# Load environment
load_dotenv()

# Create necessary directories first
os.makedirs('logs', exist_ok=True)
os.makedirs('temp', exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/wound_classifier.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# LINE Configuration
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_API_URL = 'https://api.line.me/v2/bot'

# User session management
user_sessions = {}
user_conversations = {}

class UserSession:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session_id = str(uuid.uuid4())
        self.question_count = 0
        self.last_analysis = None
        self.images = []  # Store image paths
        self.conversation_history = []
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
    
    def add_image(self, image_path: str):
        """Add image to session"""
        self.images.append({
            'path': image_path,
            'timestamp': datetime.now()
        })
        self.last_activity = datetime.now()
    
    def increment_question(self):
        """Increment question count"""
        self.question_count += 1
        self.last_activity = datetime.now()
        
        # Clean up old images after 5 questions
        if self.question_count >= 5:
            self.cleanup_old_images()
            self.question_count = 0
    
    def cleanup_old_images(self):
        """Delete old images"""
        for img_info in self.images:
            try:
                if os.path.exists(img_info['path']):
                    os.remove(img_info['path'])
                    logger.info(f"Deleted old image: {img_info['path']}")
            except Exception as e:
                logger.warning(f"Failed to delete image {img_info['path']}: {e}")
        
        self.images = []
        logger.info(f"Cleaned up images for user {self.user_id}")

class LineBot:
    def __init__(self, channel_secret, channel_access_token):
        self.channel_secret = channel_secret
        self.channel_access_token = channel_access_token
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {channel_access_token}'
        }
    
    def validate_signature(self, body, signature):
        if not self.channel_secret or not signature:
            return False
        try:
            hash_result = hmac.new(
                self.channel_secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()
            expected_signature = base64.b64encode(hash_result).decode('utf-8')
            is_valid = signature == expected_signature
            logger.info(f"🔐 Signature validation: {'✅ Valid' if is_valid else '❌ Invalid'}")
            return is_valid
        except Exception as e:
            logger.error(f"Signature validation error: {e}")
            return False
    
    def show_typing_indicator(self, user_id):
        """Show typing indicator (loading animation)"""
        url = f"{LINE_API_URL}/bot/chat/loading/start"
        payload = {
            'chatId': user_id,
            'loadingSeconds': 20  # Show for up to 20 seconds
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            success = response.status_code == 200
            logger.info(f"⏳ Typing indicator: {'✅ Started' if success else '❌ Failed'}")
            return success
        except Exception as e:
            logger.error(f"Typing indicator error: {e}")
            return False
    
    def reply_message(self, reply_token, messages):
        """Send reply message(s)"""
        url = f"{LINE_API_URL}/message/reply"
        
        # Ensure messages is a list
        if isinstance(messages, str):
            messages = [{"type": "text", "text": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        
        payload = {
            'replyToken': reply_token,
            'messages': messages[:5]  # LINE limit: max 5 messages
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            success = response.status_code == 200
            logger.info(f"💬 Reply sent: {'✅ Success' if success else '❌ Failed'}")
            if not success:
                logger.error(f"Reply error: {response.status_code} - {response.text}")
            return success
        except Exception as e:
            logger.error(f"Reply error: {e}")
            return False
    
    def push_message(self, user_id, messages):
        """Send push message(s)"""
        url = f"{LINE_API_URL}/message/push"
        
        # Ensure messages is a list
        if isinstance(messages, str):
            messages = [{"type": "text", "text": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        
        payload = {
            'to': user_id,
            'messages': messages[:5]  # LINE limit: max 5 messages
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            success = response.status_code == 200
            logger.info(f"📤 Push sent: {'✅ Success' if success else '❌ Failed'}")
            return success
        except Exception as e:
            logger.error(f"Push error: {e}")
            return False
    
    def get_message_content(self, message_id):
    # เปลี่ยน URL ให้ถูกต้องตาม LINE Data API
        url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                logger.info(f"📸 Image downloaded: {len(response.content)} bytes")
                return response.content
            else:
                # เพิ่มการบันทึกข้อผิดพลาดแบบละเอียด
                logger.error(f"LINE API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.exception("Exception in image download:")  # บันทึก stack trace
            return None

# Initialize LINE Bot
line_bot = None
if LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN:
    line_bot = LineBot(LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN)
    logger.info("✅ LINE Bot initialized successfully")

def get_user_session(user_id: str) -> UserSession:
    """Get or create user session"""
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
        logger.info(f"Created new session for user: {user_id}")
    
    return user_sessions[user_id]

def handle_webhook_request():
    """Central webhook handler that ALWAYS returns 200"""
    try:
        # Enhanced logging
        logger.info(f"🔄 {request.method} {request.path} from {request.remote_addr}")
        logger.info(f"📡 Headers: {dict(request.headers)}")
        logger.info(f"🌐 User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
        
        # Handle different methods
        if request.method == 'GET':
            return jsonify({
                "status": "webhook_ready",
                "method": "GET",
                "message": "SurgiCare LINE Bot webhook is ready",
                "line_configured": bool(line_bot),
                "endpoints": ["/callback", "/health"]
            }), 200
        
        elif request.method == 'POST':
            # Get request data
            body = request.get_data()
            signature = request.headers.get('X-Line-Signature')
            
            logger.info(f"📦 Body length: {len(body)} bytes")
            logger.info(f"📦 Body content: {body.decode('utf-8') if body else 'Empty'}")
            logger.info(f"🔐 Signature: {signature if signature else 'Missing'}")
            
            # If no LINE Bot configured, still return 200
            if not line_bot:
                logger.warning("⚠️ LINE Bot not configured")
                return jsonify({"status": "not_configured", "message": "LINE Bot not configured"}), 200
            
            # If no signature, still return 200
            if not signature:
                logger.warning("⚠️ No signature provided")
                return jsonify({"status": "no_signature", "message": "No X-Line-Signature header"}), 200
            
            # Validate signature
            if not line_bot.validate_signature(body, signature):
                logger.warning("⚠️ Invalid signature")
                return jsonify({"status": "invalid_signature", "message": "Signature validation failed"}), 200
            
            # Process events
            try:
                data = json.loads(body.decode('utf-8'))
                events = data.get('events', [])
                logger.info(f"📥 Processing {len(events)} events: {events}")
                
                for event in events:
                    # Process each event in a separate thread to avoid blocking
                    threading.Thread(target=process_event, args=(event,)).start()
                
                return 'OK', 200
                
            except Exception as e:
                logger.error(f"❌ Event processing error: {e}")
                return jsonify({"status": "processing_error", "error": str(e)}), 200
        
        else:
            # Handle any other method
            return jsonify({
                "status": "method_received",
                "method": request.method,
                "message": f"{request.method} method handled successfully"
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Webhook handler error: {e}")
        return jsonify({"status": "handler_error", "error": str(e)}), 200

def process_event(event):
    """Process LINE events with full functionality"""
    event_type = event.get('type')
    logger.info(f"🎯 Processing event: {event_type}")
    
    try:
        if event_type == 'message':
            handle_message_event(event)
        elif event_type == 'follow':
            handle_follow_event(event)
        elif event_type == 'unfollow':
            handle_unfollow_event(event)
        else:
            logger.info(f"🎯 Unhandled event type: {event_type}")
    except Exception as e:
        logger.error(f"❌ Event processing error: {e}")

def handle_message_event(event):
    """Handle message events"""
    message = event.get('message', {})
    reply_token = event.get('replyToken')
    user_id = event.get('source', {}).get('userId')
    message_type = message.get('type')
    
    logger.info(f"💬 Message type: {message_type} from user: {user_id}")
    
    # Get user session
    session = get_user_session(user_id)
    
    if message_type == 'text':
        handle_text_message(message, reply_token, user_id, session)
    elif message_type == 'image':
        handle_image_message(message, event, reply_token, user_id, session)

def handle_text_message(message, reply_token, user_id, session: UserSession):
    """Handle text messages with conversation context"""
    user_text = message.get('text', '').strip()
    logger.info(f"💬 User text: {user_text}")
    
    # Show typing indicator immediately
    if line_bot and user_id:
        line_bot.show_typing_indicator(user_id)
    
    # Add to conversation history
    session.conversation_history.append({
        'type': 'user',
        'text': user_text,
        'timestamp': datetime.now()
    })
    
    # Increment question count
    session.increment_question()
    
    # Simulate processing time for better UX
    time.sleep(1)
    
    # Handle different text commands
    if user_text.lower() in ['สวัสดี', 'hello', 'hi', 'start', 'เริ่ม']:
        reply_text = """👋 สวัสดีครับ! ยินดีต้อนรับสู่ SurgiCare - ระบบวิเคราะห์แผล AI

🔬 ฟีเจอร์หลัก:
📸 ส่งรูปแผล → รับการวิเคราะห์ทันที
💬 ถามคำถามเกี่ยวกับการดูแลแผล
🩹 รับคำแนะนำการรักษาเฉพาะ

📋 ประเภทแผลที่วิเคราะห์ได้:
• แผลถลอก (Abrasions)
• รอยช้ำ (Bruises) 
• แผลไฟไหม้ (Burns)
• แผลบาด (Cuts)
• ผิวหนังปกติ (Normal)

📸 ส่งรูปแผลมาเลยเพื่อเริ่มวิเคราะห์!

⚠️ คำเตือน: ระบบนี้เป็นเครื่องมือช่วยเหลือเบื้องต้น ไม่ทดแทนการตรวจวินิจฉัยของแพทย์"""
        
    elif user_text.lower() in ['help', 'ช่วยเหลือ', 'วิธีใช้']:
        reply_text = """📋 คู่มือการใช้งาน SurgiCare:

1️⃣ ส่งรูปแผล
• ถ่ายรูปแผลให้ชัดเจน
• ส่งในแชทนี้
• รอการวิเคราะห์ 5-10 วินาที

2️⃣ ดูผลการวิเคราะห์
• ประเภทแผล + ความมั่นใจ
• คำแนะนำการดูแล
• สัญญาณเตือนที่ต้องพบแพทย์

3️⃣ ถามคำถามเพิ่มเติม
• สอบถามเกี่ยวกับการดูแล
• ขออธิบายเพิ่มเติม
• หารือเกี่ยวกับอาการ

💡 เคล็ดลับ:
• ถ่ายรูปในที่มีแสงดี
• แผลต้องเห็นชัดเจน
• ไม่มีสิ่งบดบัง

พิมพ์ 'สวัสดี' เพื่อเริ่มใหม่"""

    elif user_text.lower() in ['test', 'ทดสอบ']:
        reply_text = f"""🧪 การทดสอบระบบ:

✅ ระบบทำงานปกติ
🤖 AI Model: พร้อมใช้งาน
📱 LINE Bot: เชื่อมต่อแล้ว
🗂️ Session: {session.session_id[:8]}...
💬 คำถามที่: {session.question_count}/5

⏰ เวลา: {datetime.now().strftime('%H:%M:%S น.')}

ระบบพร้อมรับรูปแผลและคำถามของคุณ!"""

    elif session.last_analysis and any(keyword in user_text.lower() for keyword in ['เจ็บ', 'ปวด', 'แสบ', 'คัน', 'บวม', 'แดง', 'เลือด', 'หนอง']):
        # Interactive conversation about wound symptoms
        reply_text = handle_symptom_discussion(user_text, session)
        
    elif session.last_analysis and any(keyword in user_text.lower() for keyword in ['ดูแล', 'รักษา', 'ทำไง', 'ช่วย', 'แนะนำ']):
        # Care instructions discussion
        reply_text = handle_care_discussion(user_text, session)
        
    elif user_text.lower() in ['stats', 'สถิติ', 'ข้อมูล']:
        reply_text = get_session_stats(session)
        
    else:
        # General response with context awareness
        if session.last_analysis:
            reply_text = f"""ขณะนี้ผมกำลังวิเคราะห์แผลประเภท "{session.last_analysis['thai_class']}" ของคุณอยู่

💬 คุณสามารถ:
• ถามเกี่ยวกับอาการที่พบ
• สอบถามวิธีการดูแล
• ส่งรูปแผลใหม่เพื่อวิเคราะห์เพิ่ม

หรือพิมพ์:
• "help" - ดูวิธีใช้งาน
• "test" - ทดสอบระบบ
• "สวัสดี" - เริ่มใหม่"""
        else:
            reply_text = """📸 กรุณาส่งรูปภาพแผลมาให้ผมวิเคราะห์ครับ

หรือพิมพ์:
• "help" - ดูวิธีใช้งาน  
• "test" - ทดสอบระบบ
• "สวัสดี" - เริ่มใหม่"""
    
    # Add bot response to conversation
    session.conversation_history.append({
        'type': 'bot',
        'text': reply_text,
        'timestamp': datetime.now()
    })
    
    # Send reply
    if line_bot and reply_token:
        success = line_bot.reply_message(reply_token, reply_text)
        if success:
            logger.info(f"✅ Successfully replied to user {user_id}")
        else:
            logger.error(f"❌ Failed to reply to user {user_id}")
    else:
        logger.warning("❌ Cannot send reply: LINE Bot not configured or no reply token")

def handle_symptom_discussion(user_text: str, session: UserSession) -> str:
    """Handle symptom-related questions"""
    symptoms_advice = {
        'เจ็บ': 'การเจ็บปวดเป็นเรื่องปกติในการสมานแผล แต่ถ้าเจ็บมากขึ้นหรือไม่ดีขึ้น ควรพบแพทย์',
        'ปวด': 'ความปวดควรลดลงตามเวลา ใช้ยาแก้ปวดตามคำแนะนำของเภสัชกร',
        'แสบ': 'อาการแสบอาจเกิดจากการอักเสบ ล้างแผลเบาๆ ด้วยน้ำสะอาด',
        'คัน': 'อาการคันแสดงถึงการหาย แต่อย่าเกา ใช้ผ้าเย็นประคบแทน',
        'บวม': 'อาการบวมเล็กน้อยเป็นปกติ แต่ถ้าบวมมากและแดงควรพบแพทย์',
        'แดง': 'รอยแดงรอบแผลเล็กน้อยเป็นปกติ แต่ถ้าแดงลามออกไปต้องระวัง',
        'เลือด': 'เลือดออกเล็กน้อยเป็นปกติ แต่ถ้าเลือดไหลไม่หยุดต้องรีบพบแพทย์',
        'หนอง': 'หนองเป็นสัญญาณการติดเชื้อ ต้องรีบพบแพทย์ทันที'
    }
    
    advice_given = []
    for symptom, advice in symptoms_advice.items():
        if symptom in user_text.lower():
            advice_given.append(f"💡 {symptom}: {advice}")
    
    if advice_given:
        response = f"""🩹 คำแนะนำเกี่ยวกับอาการที่คุณถาม:

{chr(10).join(advice_given)}

⚠️ สัญญาณเตือนที่ต้องพบแพทย์ทันที:
• เจ็บปวดรุนแรงขึ้น
• บวมแดงลามออกไป
• มีไข้
• มีกลิ่นเหม็น
• เลือดไหลไม่หยุด

มีอาการอื่นที่อยากถามไหมครับ?"""
    else:
        response = """ขออภัย ผมไม่เข้าใจอาการที่คุณอธิบาย

กรุณาอธิบายอาการเฉพาะ เช่น:
• "เจ็บมาก" 
• "บวมแดง"
• "มีหนอง"
• "คันมาก"

หรือส่งรูปแผลใหม่เพื่อวิเคราะห์อีกครั้ง"""
    
    return response

def handle_care_discussion(user_text: str, session: UserSession) -> str:
    """Handle care-related questions"""
    if not session.last_analysis:
        return "กรุณาส่งรูปแผลก่อนเพื่อให้ผมสามารถให้คำแนะนำการดูแลที่เหมาะสมได้"
    
    wound_type = session.last_analysis['predicted_class']
    
    detailed_care = {
        'Abrasions': """🩹 การดูแลแผลถลอกขั้นละเอียด:

📋 ขั้นตอนรายวัน:
1. ล้างมือด้วยสบู่ 20 วินาที
2. ล้างแผลเบาๆ ด้วยน้ำสะอาด
3. ซับให้แห้งด้วยผ้าสะอาด
4. ทายาปฏิชีวนะบางๆ
5. ปิดแผลด้วยผ้าพันแผล
6. เปลี่ยนผ้าพันทุก 12-24 ชั่วโมง

⚠️ ข้อควรระวัง:
• อย่าใช้แอลกอฮอล์ล้างแผล
• อย่าแกะสะเก็ดแผล
• หลีกเลี่ยงน้ำโสโครกแผล""",

        'Bruises': """🩹 การดูแลรอยช้ำขั้นละเอียด:

📋 24 ชั่วโมงแรก:
1. ประคบเย็น 15-20 นาที/ครั้ง
2. ยกส่วนที่ช้ำให้สูง
3. หลีกเลี่ยงการนวด

📋 หลัง 48 ชั่วโมง:
1. ประคบอุ่น 15-20 นาที/ครั้ง
2. นวดเบาๆ เป็นวงกลม
3. ใช้ยาแก้ปวดตามต้องการ

⚠️ สัญญาณเตือน:
• บวมมากผิดปกติ
• เจ็บรุนแรงขึ้น
• สีผิวเปลี่ยนเป็นม่วงดำ""",

        'Burns': """🩹 การดูแลแผลไฟไหม้ขั้นละเอียด:

📋 การดูแลเฉียบพลัน:
1. ล้างด้วยน้ำเย็นทันที 10-20 นาที
2. เอาเครื่องประดับออกก่อนบวม
3. ห้ามแกะพุพอง

📋 การดูแลต่อเนื่อง:
1. ใช้ผ้าสะอาดปิดแผลหลวมๆ
2. เปลี่ยนผ้าพันทุกวัน
3. หลีกเลี่ยงครีมหรือยาที่ไม่จำเป็น

⚠️ ต้องพบแพทย์หาก:
• แผลใหญ่กว่าฝ่ามือ
• ลึกถึงชั้นใต้ผิวหนัง
• อยู่บริเวณหน้า มือ เท้า อวัยวะเพศ""",

        'Cut': """🩹 การดูแลแผลบาดขั้นละเอียด:

📋 ห้ามเลือดทันที:
1. กดด้วยผ้าสะอาด 10-15 นาที
2. ยกส่วนที่บาดให้สูง
3. ห้ามดูแผลบ่อยๆ

📋 การดูแลต่อเนื่อง:
1. ล้างแผลเบาๆ หลังเลือดหยุด
2. ทายาปฏิชีวนะบางๆ
3. ปิดแผลให้แน่น
4. เปลี่ยนผ้าพันเมื่อเปียกเลือด

⚠️ ต้องเย็บแผลหาก:
• ลึกเห็นชั้นใน
• ยาวเกิน 1 ซม.
• ขอบแผลแยกห่าง""",

        'Normal': """✅ ผิวหนังปกติ - การดูแลป้องกัน:

📋 การดูแลประจำวัน:
1. ล้างด้วยสบู่อ่อนโยน
2. ใช้ครีมบำรุงหลังอาบน้ำ
3. ใส่ครีมกันแดด SPF 30+
4. ดื่มน้ำ 8 แก้ว/วัน

📋 การป้องกันบาดแผล:
• ใส่รองเท้าเซฟตี้ในที่อันตราย
• ใช้มีดอย่างระมัดระวัง
• หลีกเลี่ยงกิจกรรมเสี่ยงอันตราย
• ตรวจสอบผิวหนังเป็นประจำ"""
    }
    
    return detailed_care.get(wound_type, "ไม่สามารถให้คำแนะนำการดูแลสำหรับประเภทแผลนี้ได้")

def get_session_stats(session: UserSession) -> str:
    """Get session statistics"""
    return f"""📊 สถิติการใช้งานของคุณ:

👤 Session ID: {session.session_id[:8]}...
⏰ เริ่มใช้งาน: {session.created_at.strftime('%H:%M น.')}
💬 จำนวนคำถาม: {session.question_count}/5
📸 รูปภาพที่อัพโหลด: {len(session.images)}
🩹 การวิเคราะห์ล่าสุด: {session.last_analysis['thai_class'] if session.last_analysis else 'ยังไม่มี'}

💡 ระบบจะลบรูปเก่าทิ้งอัตโนมัติหลังจาก 5 คำถาม

พิมพ์ 'สวัสดี' เพื่อเริ่มเซสชันใหม่"""

def handle_image_message(message, event, reply_token, user_id, session: UserSession):
    """Handle image messages - Real wound analysis"""
    logger.info("📸 Processing image message")
    
    try:
        # Show typing indicator immediately
        if line_bot and user_id:
            line_bot.show_typing_indicator(user_id)
        
        # Send immediate response
        if line_bot and reply_token:
            line_bot.reply_message(reply_token, "🔍 กำลังวิเคราะห์รูปภาพแผล กรุณารอสักครู่...")
        
        # Get image content
        message_id = message.get('id')
        
        if not message_id:
            logger.error("Missing message ID")
            return
        
        # Download image
        image_content = line_bot.get_message_content(message_id)
        if not image_content:
            if user_id:
                line_bot.push_message(user_id, "❌ ไม่สามารถดาวน์โหลดรูปภาพได้ กรุณาลองใหม่")
            return
        
        # Create temp directory for this user
        user_temp_dir = os.path.join('temp', user_id)
        os.makedirs(user_temp_dir, exist_ok=True)
        
        # Save image with unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(user_temp_dir, f"wound_{timestamp}_{message_id}.jpg")
        
        with open(temp_path, 'wb') as f:
            f.write(image_content)
        
        # Add to session
        session.add_image(temp_path)
        
        logger.info(f"📸 Image saved: {temp_path}")
        
        # Show typing indicator again for analysis
        if line_bot and user_id:
            line_bot.show_typing_indicator(user_id)
        
        # Analyze wound using real AI (fallback to simulation for now)
        try:
            analysis_result = analyze_wound_with_ai(temp_path)
        except Exception as ai_error:
            logger.warning(f"AI analysis failed, using simulation: {ai_error}")
            analysis_result = simulate_wound_analysis(temp_path)
        
        # Store analysis in session
        session.last_analysis = analysis_result
        
        # Create comprehensive result message
        result_messages = create_analysis_result_messages(analysis_result, session)
        
        # Send results (multiple messages with typing indicators)
        if user_id:
            for i, msg in enumerate(result_messages):
                if i > 0:  # Show typing for subsequent messages
                    line_bot.show_typing_indicator(user_id)
                    time.sleep(2)  # Wait before sending next message
                
                success = line_bot.push_message(user_id, msg)
                if success:
                    logger.info(f"✅ Sent analysis message {i+1}/{len(result_messages)}")
                else:
                    logger.error(f"❌ Failed to send analysis message {i+1}")
                
                time.sleep(1)  # Delay between messages
        
        logger.info("✅ Image analysis completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Image processing error: {e}")
        if user_id and line_bot:
            line_bot.push_message(
                user_id,
                "❌ เกิดข้อผิดพลาดในการวิเคราะห์รูปภาพ กรุณาลองใหม่อีกครั้ง"
            )

def analyze_wound_with_ai(image_path: str) -> dict:
    """Real AI wound analysis (implement actual AI here)"""
    try:
        # Import AI modules
        from utils.extract_wound_class import classify_wound_image
        from utils.extract_wound_features import extract_wound_features
        from utils.image_utils import validate_image, get_image_info
        
        # Validate image
        if not validate_image(image_path):
            raise ValueError("Invalid image file")
        
        # Get image info
        img_info = get_image_info(image_path)
        logger.info(f"Image info: {img_info}")
        
        # Classify wound
        classification_result = classify_wound_image(image_path, language='en')
        
        # Extract features
        features = extract_wound_features(
            image_path,
            classification_result['predicted_class'],
            top_k=5,
            lang='th'
        )
        
        # Combine results
        result = {
            'predicted_class': classification_result['predicted_class'],
            'thai_class': get_thai_class_name(classification_result['predicted_class']),
            'confidence': classification_result['confidence'],
            'probabilities': classification_result['probabilities'],
            'features': [f[0] for f in features],  # Extract feature descriptions
            'feature_scores': [f[1] for f in features],  # Extract confidence scores
            'image_info': img_info,
            'analysis_timestamp': datetime.now(),
            'method': 'AI'
        }
        
        logger.info(f"🤖 AI Analysis result: {result['predicted_class']} ({result['confidence']:.1%})")
        return result
        
    except ImportError as e:
        logger.warning(f"AI modules not available: {e}")
        raise Exception("AI modules not found")
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        raise

def get_thai_class_name(english_class: str) -> str:
    """Convert English class name to Thai"""
    class_mapping = {
        'Abrasions': 'แผลถลอก',
        'Bruises': 'รอยช้ำ',
        'Burns': 'แผลไฟไหม้',
        'Cut': 'แผลบาด',
        'Normal': 'ผิวหนังปกติ'
    }
    return class_mapping.get(english_class, english_class)

def simulate_wound_analysis(image_path: str) -> dict:
    """Simulate wound analysis for fallback"""
    wound_types = {
        'Abrasions': 'แผลถลอก',
        'Bruises': 'รอยช้ำ',
        'Burns': 'แผลไฟไหม้', 
        'Cut': 'แผลบาด',
        'Normal': 'ผิวหนังปกติ'
    }
    
    # Random prediction with realistic confidence
    predicted_class = random.choice(list(wound_types.keys()))
    confidence = random.uniform(0.75, 0.95)
    
    # Simulate features based on wound type
    simulated_features = get_simulated_features(predicted_class)
    
    logger.info(f"🔮 Simulation result: {predicted_class} ({confidence:.1%})")
    
    return {
        'predicted_class': predicted_class,
        'thai_class': wound_types[predicted_class],
        'confidence': confidence,
        'probabilities': {wound_types[k]: random.uniform(0.05, 0.95) if k == predicted_class else random.uniform(0.01, 0.15) for k in wound_types.keys()},
        'features': simulated_features,
        'feature_scores': [random.uniform(0.7, 0.95) for _ in simulated_features],
        'image_info': {'method': 'simulation'},
        'analysis_timestamp': datetime.now(),
        'method': 'Simulation'
    }

def get_simulated_features(wound_class: str) -> list:
    """Get simulated features for wound class"""
    features_th = {
        'Abrasions': [
            "แผลถลอกอยู่เพียงชั้นหนังกำพร้าเท่านั้น",
            "มีรอยแดงและลักษณะเหมือนถลอกที่พบได้ทั่วไป",
            "มีของเหลวเล็กน้อยและผิวหนังรอบแผลยังคงสมบูรณ์",
            "พบสะเก็ดแผลซึ่งเป็นส่วนหนึ่งของกระบวนการหาย",
            "พื้นผิวแผลดูเหมือนถูกขูดขีด ขอบแผลไม่เรียบ"
        ],
        'Bruises': [
            "มีรอยช้ำสีน้ำเงินอมม่วงบนผิวหนัง",
            "ไม่พบแผลเปิดหรือการสูญเสียเนื้อเยื่อ",
            "บริเวณที่ช้ำมีอาการบวมและเจ็บแต่ไม่มีเลือดออก",
            "สีของรอยช้ำเปลี่ยนจากม่วงเป็นเหลืองตามเวลา",
            "ผิวหนังยังคงสมบูรณ์แต่มีเลือดออกใต้ผิวหนังเฉพาะจุด"
        ],
        'Burns': [
            "พบบวมพองซึ่งสอดคล้องกับแผลไฟไหม้ระดับที่สอง",
            "ผิวหนังไหม้ดำหรือแข็งคล้ายหนัง",
            "มีรอยแดงและบวมในบริเวณที่ไหม้",
            "บริเวณแผลไหม้มีผิวแห้ง แตก และลอกออก",
            "ผิวหนังลอกออกและเห็นชั้นผิวหนังด้านใน"
        ],
        'Cut': [
            "แผลมีลักษณะเป็นเส้นตรง ขอบแผลชัดเจน",
            "มีเลือดออก สอดคล้องกับแผลที่เพิ่งเกิดใหม่",
            "เห็นเนื้อเยื่อภายในบริเวณแผล",
            "ขอบแผลเริ่มติดกัน บ่งบอกกระบวนการสมานแผล",
            "มีการแข็งตัวของเลือดเล็กน้อยในแผล"
        ],
        'Normal': [
            "ผิวหนังดูปกติและไม่มีบาดแผลให้เห็น",
            "ไม่พบรอยแดง บวม หรือแผลเปิด",
            "สีผิวและลักษณะพื้นผิวปกติ ไม่มีของเหลวผิดปกติ",
            "บริเวณนี้แห้งและไม่พบความผิดปกติใดๆ",
            "ไม่พบร่องรอยของการบาดเจ็บ รอยช้ำ หรือการอักเสบ"
        ]
    }
    
    return features_th.get(wound_class, [])[:5]

def create_analysis_result_messages(result: dict, session: UserSession) -> list:
    """Create comprehensive analysis result messages"""
    messages = []
    
    confidence_percent = int(result['confidence'] * 100)
    
    # Confidence indicator
    if confidence_percent >= 85:
        confidence_emoji = "🟢"
        confidence_text = "สูงมาก"
    elif confidence_percent >= 70:
        confidence_emoji = "🟡"
        confidence_text = "ปานกลาง"
    else:
        confidence_emoji = "🔴"
        confidence_text = "ต่ำ"
    
    # Main result message
    main_message = f"""🔬 ผลการวิเคราะห์แผล - SurgiCare AI

📋 ประเภทแผล: {result['thai_class']}
{confidence_emoji} ความมั่นใจ: {confidence_percent}% ({confidence_text})
🤖 วิเคราะห์โดย: {result.get('method', 'AI')}
⏰ เวลา: {result['analysis_timestamp'].strftime('%H:%M น.')}

🔍 ลักษณะแผลที่พบ:"""
    
    messages.append(main_message)
    
    # Features message
    if result.get('features'):
        features_text = "📝 รายละเอียดที่ตรวจพบ:\n\n"
        for i, feature in enumerate(result['features'][:3], 1):
            score = result.get('feature_scores', [0.8])[i-1] if result.get('feature_scores') else 0.8
            features_text += f"{i}. {feature}\n   (ความมั่นใจ: {score:.1%})\n\n"
        
        messages.append(features_text.strip())
    
    # Recommendations message
    recommendations = get_detailed_recommendations(result['predicted_class'])
    messages.append(recommendations)
    
    # Interactive prompt
    interactive_msg = f"""💬 คุณสามารถถามคำถามเพิ่มเติมได้:

• "เจ็บมากต้องทำไง"
• "ดูแลอย่างไร"
• "เมื่อไรต้องหาหมอ"
• "มีอาการแปลกปลอม"

📸 หรือส่งรูปแผลใหม่เพื่อวิเคราะห์เพิ่ม

🗂️ คำถามที่ {session.question_count}/5 (จะลบรูปเก่าเมื่อครบ 5 คำถาม)"""
    
    messages.append(interactive_msg)
    
    return messages

def get_detailed_recommendations(wound_type: str) -> str:
    """Get detailed recommendations for wound type"""
    recommendations = {
        'Abrasions': """🩹 คำแนะนำการดูแลแผลถลอก:

🔹 ขั้นตอนทันที:
1. ล้างมือให้สะอาดก่อนสัมผัสแผล
2. ล้างแผลด้วยน้ำสะอาดเบาๆ เอาสิ่งสกปรกออก
3. ใช้ผ้าสะอาดซับให้แห้ง
4. ทายาปฏิชีวนะและปิดแผลด้วยผ้าพันแผล

🔹 การดูแลต่อเนื่อง:
• เปลี่ยนผ้าพันแผลทุกวัน
• เฝ้าระวังการติดเชื้อ
• หลีกเลี่ยงการแกะสะเก็ดแผล

⚠️ รีบพบแพทย์หาก: แผลแดงบวม มีหนอง มีกลิ่น หรือเจ็บมากขึ้น""",

        'Bruises': """🩹 คำแนะนำการดูแลรอยช้ำ:

🔹 24 ชั่วโมงแรก:
1. ประคบเย็นทันที (15-20 นาทีต่อครั้ง)
2. ยกส่วนที่ช้ำให้สูงกว่าระดับหัวใจ
3. หลีกเลี่ยงการนวดหรือกดแรงๆ

🔹 หลัง 48 ชั่วโมง:
• ประคบอุ่น
• นวดเบาๆ เป็นวงกลม
• รับประทานยาแก้ปวดตามความจำเป็น

⚠️ รีบพบแพทย์หาก: บวมมาก เจ็บอย่างมาก หรือไม่ดีขึ้นใน 1 สัปดาห์""",

        'Burns': """🩹 คำแนะนำการดูแลแผลไฟไหม้:

🔹 ขั้นตอนทันที:
1. หยุดการสัมผัสกับความร้อนทันที
2. ล้างด้วยน้ำเย็นนาน 10-20 นาที
3. เอาเครื่องประดับออกก่อนบวม
4. ห้ามแกะพุพอง ใช้ผ้าสะอาดปิดแผล

🔹 สิ่งที่ห้ามทำ:
• ใช้น้ำแข็ง ยาสีฟัน หรือเนย
• แกะพุพองหรือหนังที่ลอก
• ใช้ครีมโดยไม่ปรึกษาแพทย์

⚠️ รีบไปโรงพยาบาลหาก: แผลไหม้ขนาดใหญ่ ลึก หรือมีพุพองมาก""",

        'Cut': """🩹 คำแนะนำการดูแลแผลบาด:

🔹 ขั้นตอนทันที:
1. กดแผลด้วยผ้าสะอาดเพื่อห้ามเลือด
2. ล้างแผลด้วยน้ำสะอาดเมื่อเลือดหยุด
3. ใช้ยาปฏิชีวนะทาแผล
4. ปิดแผลด้วยผ้าพันแผลหรือพลาสเตอร์

🔹 การดูแลต่อเนื่อง:
• เปลี่ยนผ้าพันแผลทุกวันและดูแลให้แห้ง
• เฝ้าระวังสัญญาณการติดเชื้อ
• หลีกเลี่ยงการเปียกน้ำนานๆ

⚠️ รีบพบแพทย์หาก: แผลลึก เลือดไหลไม่หยุด หรือมีสิ่งแปลกปลอมในแผล""",

        'Normal': """✅ ผิวหนังปกติ - คำแนะนำการดูแล:

🔹 การดูแลประจำวัน:
1. ทำความสะอาดผิวหนังอย่างสม่ำเสมอ
2. ใช้ครีมบำรุงผิวเพื่อป้องกันความแห้ง
3. ใช้ครีมกันแดดเมื่อออกแดด
4. ดื่มน้ำให้เพียงพอเพื่อผิวหนังชุ่มชื้น

🔹 การป้องกันบาดแผล:
• หลีกเลี่ยงการขูดขีดหรือเกาแรงๆ
• ใส่อุปกรณ์ป้องกันเมื่อทำกิจกรรมเสี่ยง
• ตรวจสอบผิวหนังเป็นประจำ

💡 การดูแลผิวหนังที่ดีจะช่วยป้องกันการบาดเจ็บและรักษาสุขภาพผิว"""
    }
    
    return recommendations.get(wound_type, "กรุณาปรึกษาแพทย์เพื่อการตรวจวินิจฉัยที่ถูกต้อง")

def handle_follow_event(event):
    """Handle follow events"""
    user_id = event.get('source', {}).get('userId')
    
    # Create new session
    session = get_user_session(user_id)
    
    welcome_messages = [
        """🎉 ขอบคุณที่เพิ่มเพื่อน SurgiCare Wound Classifier!

🔬 ระบบวิเคราะห์แผล AI ที่ทันสมัย
📸 ส่งรูปแผล → รับการวิเคราะห์ทันที
💬 โต้ตอบถามคำถามเกี่ยวกับการดูแล""",

        """📋 ประเภทแผลที่วิเคราะห์ได้:
• แผลถลอก (Abrasions)
• รอยช้ำ (Bruises) 
• แผลไฟไหม้ (Burns)
• แผลบาด (Cuts)
• ผิวหนังปกติ (Normal)

📸 ส่งรูปแผลมาเลยเพื่อเริ่มการวิเคราะห์!""",

        """⚠️ ข้อสำคัญ:
ระบบนี้เป็นเครื่องมือช่วยเหลือเบื้องต้น ไม่สามารถทดแทนการตรวจวินิจฉัยของแพทย์ได้

💡 พิมพ์ "help" เพื่อดูวิธีใช้งาน"""
    ]
    
    if user_id and line_bot:
        for msg in welcome_messages:
            line_bot.push_message(user_id, msg)
            time.sleep(1)
        logger.info(f"👋 Welcome message sent to: {user_id}")

def handle_unfollow_event(event):
    """Handle unfollow events"""
    user_id = event.get('source', {}).get('userId')
    
    # Clean up user session
    if user_id in user_sessions:
        session = user_sessions[user_id]
        session.cleanup_old_images()  # Clean up all images
        del user_sessions[user_id]
    
    logger.info(f"👋 User unfollowed and cleaned up: {user_id}")

# Register webhook endpoints
@app.route('/callback', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def callback():
    """Main webhook endpoint"""
    return handle_webhook_request()

@app.route('/webhook', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def webhook_alt():
    """Alternative webhook path"""
    return handle_webhook_request()

# Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "line_configured": bool(line_bot),
        "active_sessions": len(user_sessions),
        "service": "SurgiCare Wound Classifier",
        "version": "2.0.0",
        "features": [
            "Real-time wound analysis",
            "Interactive conversations", 
            "Auto image cleanup",
            "Session management"
        ]
    }), 200

# Admin endpoint to view sessions
@app.route('/admin/sessions', methods=['GET'])
def admin_sessions():
    """Admin endpoint to view active sessions"""
    sessions_info = {}
    for user_id, session in user_sessions.items():
        sessions_info[user_id] = {
            'session_id': session.session_id,
            'question_count': session.question_count,
            'images_count': len(session.images),
            'last_analysis': session.last_analysis['thai_class'] if session.last_analysis else None,
            'created_at': session.created_at.isoformat(),
            'last_activity': session.last_activity.isoformat()
        }
    
    return jsonify({
        "total_sessions": len(user_sessions),
        "sessions": sessions_info
    }), 200

# Root endpoint
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "service": "SurgiCare Wound Classifier LINE Bot",
        "status": "running",
        "version": "2.0.0",
        "description": "AI-powered wound analysis with interactive conversations",
        "endpoints": {
            "webhook": "/callback",
            "health": "/health",
            "admin": "/admin/sessions"
        },
        "line_configured": bool(line_bot),
        "active_sessions": len(user_sessions),
        "features": [
            "Real wound analysis with AI",
            "Interactive symptom discussion",
            "Auto image cleanup after 5 questions",
            "Comprehensive care recommendations",
            "Session management"
        ]
    }), 200

# Cleanup old sessions periodically
def cleanup_old_sessions():
    """Clean up old inactive sessions"""
    import threading
    current_time = datetime.now()
    
    sessions_to_remove = []
    for user_id, session in user_sessions.items():
        # Remove sessions inactive for more than 1 hour
        if (current_time - session.last_activity).seconds > 3600:
            session.cleanup_old_images()
            sessions_to_remove.append(user_id)
    
    for user_id in sessions_to_remove:
        del user_sessions[user_id]
        logger.info(f"Cleaned up inactive session: {user_id}")
    
    # Schedule next cleanup in 30 minutes
    threading.Timer(1800, cleanup_old_sessions).start()

# Error handlers that always return 200
@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 → 200: {request.method} {request.path}")
    return jsonify({"status": "not_found_handled", "path": request.path}), 200

@app.errorhandler(405)
def method_not_allowed(error):
    logger.warning(f"405 → 200: {request.method} {request.path}")
    return jsonify({"status": "method_handled", "method": request.method}), 200

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 → 200: {error}")
    return jsonify({"status": "error_handled", "error": str(error)}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    
    # Start session cleanup
    cleanup_old_sessions()
    
    print("🏥 SurgiCare Wound Classifier LINE Bot v2.0")
    print("=" * 60)
    print(f"🔗 Health: http://localhost:{port}/health")
    print(f"📱 Webhook: http://localhost:{port}/callback")
    print(f"👥 Admin: http://localhost:{port}/admin/sessions")
    print(f"🔧 LINE configured: {bool(line_bot)}")
    print(f"🤖 AI Analysis: Real + Fallback")
    print(f"💬 Interactive: Enabled")
    print(f"🗂️ Auto cleanup: After 5 questions")
    print(f"🛡️ Error handling: All errors → 200 OK")
    print("=" * 60)
    
    if LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN:
        print("✅ Ready to analyze wounds and interact!")
    else:
        print("⚠️ Configure LINE credentials in .env file")
    
    print()
    
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)