import requests
import json
import logging
from typing import List, Dict, Optional
from pydantic import ValidationError

from models import TyphoonAPIRequest, TyphoonAPIResponse

logger = logging.getLogger(__name__)

class TyphoonClient:
    """Client for Typhoon API integration"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.opentyphoon.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, request: TyphoonAPIRequest) -> Optional[TyphoonAPIResponse]:
        """Make a request to Typhoon API"""
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=request.dict(),
                timeout=30
            )
            
            if response.status_code == 200:
                response_data = response.json()
                return TyphoonAPIResponse(**response_data)
            else:
                logger.error(f"Typhoon API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Typhoon API request timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Typhoon API request error: {str(e)}")
            return None
        except ValidationError as e:
            logger.error(f"Typhoon API response validation error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Typhoon API request: {str(e)}")
            return None
    
    def get_wound_recommendations(
        self, 
        wound_type: str, 
        confidence: float, 
        features: List[str]
    ) -> str:
        """Get wound care recommendations from Typhoon API"""
        
        # Create system prompt
        system_prompt = """คุณเป็นแพทย์ผู้เชี่ยวชาญด้านการดูแลแผล กรุณาให้คำแนะนำการดูแลแผลที่เหมาะสมและปลอดภัย

หลักการให้คำแนะนำ:
1. ให้คำแนะนำเบื้องต้นที่ปลอดภัย
2. เน้นความสำคัญของการปรึกษาแพทย์หากจำเป็น
3. ใช้ภาษาที่เข้าใจง่าย
4. ระบุสัญญาณเตือนที่ต้องรีบพบแพทย์
5. ตอบเป็นภาษาไทยเท่านั้น"""
        
        # Create user prompt
        features_text = "\n".join([f"- {feature}" for feature in features])
        user_prompt = f"""ประเภทแผล: {wound_type}
ความมั่นใจของระบบ: {confidence:.1%}

ลักษณะแผลที่พบ:
{features_text}

กรุณาให้คำแนะนำการดูแลแผลที่เหมาะสม รวมถึง:
1. การทำความสะอาดแผล
2. การปฐมพยาบาล
3. การดูแลติดตาม
4. สัญญาณเตือนที่ต้องพบแพทย์

คำแนะนำควรมีความยาวประมาณ 150-200 คำ"""
        
        # Create API request
        try:
            api_request = TyphoonAPIRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.3,  # Lower temperature for medical advice
                top_p=0.9
            )
            
            # Make request
            response = self._make_request(api_request)
            
            if response and response.choices:
                recommendation = response.choices[0]["message"]["content"].strip()
                return self._post_process_recommendation(recommendation, wound_type)
            else:
                return self._get_fallback_recommendation(wound_type)
                
        except Exception as e:
            logger.error(f"Error getting wound recommendations: {str(e)}")
            return self._get_fallback_recommendation(wound_type)
    
    def _post_process_recommendation(self, recommendation: str, wound_type: str) -> str:
        """Post-process the recommendation to ensure safety"""
        
        # Add disclaimer if not present
        disclaimer = "\n\n⚠️ หมายเหตุ: คำแนะนำนี้เป็นเพียงข้อมูลเบื้องต้น หากมีอาการรุนแรงหรือไม่ดีขึ้น กรุณาปรึกษาแพทย์ทันที"
        
        if "ปรึกษาแพทย์" not in recommendation and "พบแพทย์" not in recommendation:
            recommendation += disclaimer
        
        return recommendation
    
    def _get_fallback_recommendation(self, wound_type: str) -> str:
        """Get fallback recommendation when API fails"""
        
        fallback_recommendations = {
            'Abrasions': """การดูแลแผลถลอก:
1. ล้างมือให้สะอาดก่อนสัมผัสแผล
2. ล้างแผลด้วยน้ำสะอาดเบาๆ เอาสิ่งสกปรกออก
3. ใช้ผ้าสะอาดซับให้แห้ง
4. ทายาปฏิชีวนะและปิดแผลด้วยผ้าพันแผล
5. เปลี่ยนผ้าพันแผลทุกวัน

สัญญาณเตือน: หากแผลแดงบวม มีหนอง มีกลิ่น หรือเจ็บมากขึ้น ให้รีบพบแพทย์""",
            
            'Bruises': """การดูแลรอยช้ำ:
1. ประคบเย็นในช่วง 24 ชั่วโมงแรก (15-20 นาทีต่อครั้ง)
2. ยกส่วนที่ช้ำให้สูงกว่าระดับหัวใจ
3. หลีกเลี่ยงการนวดหรือกดแรงๆ
4. ประคบอุ่นหลังจาก 48 ชั่วโมง
5. รับประทานยาแก้ปวดตามความจำเป็น

สัญญาณเตือน: หากบวมมาก เจ็บอย่างมาก หรือไม่ดีขึ้นใน 1 สัปดาห์ ให้พบแพทย์""",
            
            'Burns': """การดูแลแผลไฟไหม้:
1. หยุดการสัมผัสกับความร้อนทันที
2. ล้างด้วยน้ำเย็นนาน 10-20 นาที
3. เอาเครื่องประดับออกก่อนบวม
4. ห้ามแกะพุพอง ใช้ผ้าสะอาดปิดแผล
5. หลีกเลี่ยงน้ำแข็ง ยาสีฟัน หรือเนย

สัญญาณเตือน: แผลไหม้ขนาดใหญ่ ลึก หรือมีพุพองมาก ให้รีบไปโรงพยาบาล""",
            
            'Cut': """การดูแลแผลบาด:
1. กดแผลด้วยผ้าสะอาดเพื่อห้ามเลือด
2. ล้างแผลด้วยน้ำสะอาดเมื่อเลือดหยุด
3. ใช้ยาปฏิชีวนะทาแผล
4. ปิดแผลด้วยผ้าพันแผลหรือพลาสเตอร์
5. เปลี่ยนผ้าพันแผลทุกวันและดูแลให้แห้ง

สัญญาณเตือน: หากแผลลึก เลือดไหลไม่หยุด หรือมีสิ่งแปลกปลอมในแผล ให้รีบพบแพทย์""",
            
            'Normal': """ผิวหนังปกติ:
ผิวหนังของคุณดูปกติดี! 
1. ทำความสะอาดผิวหนังอย่างสม่ำเสมอ
2. ใช้ครีมบำรุงผิวเพื่อป้องกันความแห้ง
3. หลีกเลี่ยงการขูดขีดหรือเกาแรงๆ
4. ใช้ครีมกันแดดเมื่อออกแดด
5. ดื่มน้ำให้เพียงพอเพื่อผิวหนังชุ่มชื้น

การดูแลผิวหนังที่ดีจะช่วยป้องกันการบาดเจ็บและรักษาสุขภาพผิว"""
        }
        
        recommendation = fallback_recommendations.get(wound_type, 
            "ไม่สามารถระบุประเภทแผลได้ กรุณาปรึกษาแพทย์เพื่อการตรวจวินิจฉัยที่ถูกต้อง")
        
        return recommendation + "\n\n⚠️ คำแนะนำนี้เป็นเพียงข้อมูลเบื้องต้น กรุณาปรึกษาแพทย์หากมีข้อสงสัย"
    
    def get_health_tips(self, topic: str = "general") -> str:
        """Get general health tips from Typhoon API"""
        
        system_prompt = """คุณเป็นผู้เชี่ยวชาญด้านสุขภาพและการดูแลตนเอง ให้คำแนะนำที่มีประโยชน์และปฏิบัติได้จริง ตอบเป็นภาษาไทย"""
        
        user_prompt = f"ให้คำแนะนำสุขภาพเกี่ยวกับ {topic} ในรูปแบบที่เข้าใจง่ายและปฏิบัติได้จริง ประมาณ 100-150 คำ"
        
        try:
            api_request = TyphoonAPIRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            response = self._make_request(api_request)
            
            if response and response.choices:
                return response.choices[0]["message"]["content"].strip()
            else:
                return "ดูแลสุขภาพด้วยการกินอาหารครบ 5 หมู่ ออกกำลังกายสม่ำเสมอ นอนหลับพักผ่อนเพียงพอ และตรวจสุขภาพประจำปี"
                
        except Exception as e:
            logger.error(f"Error getting health tips: {str(e)}")
            return "ดูแลสุขภาพด้วยการกินอาหารครบ 5 หมู่ ออกกำลังกายสม่ำเสมอ นอนหลับพักผ่อนเพียงพอ และตรวจสุขภาพประจำปี"
    
    def test_connection(self) -> bool:
        """Test connection to Typhoon API"""
        try:
            test_request = TyphoonAPIRequest(
                messages=[
                    {"role": "user", "content": "สวัสดี"}
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            response = self._make_request(test_request)
            return response is not None
            
        except Exception as e:
            logger.error(f"Error testing Typhoon connection: {str(e)}")
            return False