# นำเข้าไลบรารีที่จำเป็นสำหรับการทำนายด้วย AI
import joblib  # สำหรับโหลดและบันทึก AI model
import pandas as pd  # สำหรับจัดการข้อมูลแบบ DataFrame
import yaml  # สำหรับอ่านไฟล์การตั้งค่า
from db import save_prediction  # ฟังก์ชันสำหรับบันทึกผลการทำนาย

# อ่านไฟล์การตั้งค่าจาก config.yaml
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# พยายามโหลด AI model ที่ผ่านการเทรนแล้ว
try:
    model = joblib.load(config['model']['path'])
    print(f"✅ โหลด AI model สำเร็จ")
except:
    # ถ้าไม่พบ model ให้แจ้งเตือนให้รัน train_model.py ก่อน
    model = None
    print(f"⚠️  ไม่พบ model ให้รัน train_model.py ก่อนครับ")

def analyze_cause(data):
    """วิเคราะห์สาเหตุและให้คำแนะนำสำหรับความผิดปกติ"""
    causes      = []  # รายการสาเหตุที่เป็นไปได้
    suggestions = []  # รายการคำแนะนำในการแก้ไข

    # ตรวจสอบสถานะ admin down
    if data['is_admin_down']:
        causes.append("Port ถูกปิดด้วยคำสั่ง shutdown")
        suggestions.append(f"no shutdown บน {data['intf']}")
    # ตรวจสอบสถานะ port up แต่ protocol down
    elif data['status_num'] == 1 and data['protocol_num'] == 0:
        causes.append("Port up แต่ Protocol down (Link down)")
        suggestions.append("ตรวจสอบสายและอุปกรณ์ปลายทาง")
    # ตรวจสอบสถานะ physical down
    elif data['status_num'] == 0:
        causes.append("Port ไม่ทำงาน (Physical down)")
        suggestions.append("ตรวจสอบสายและการเชื่อมต่อ")

    # ตรวจสอบ traffic ขาออกสูง
    if data['network_load'] > config['model']['threshold_load']:
        pct = round(data['network_load'] / 255 * 100, 1)
        causes.append(f"Traffic ขาออกสูง ({pct}%)")
        suggestions.append("ตรวจสอบ traffic อาจมี loop หรือ flood")

    # ตรวจสอบ traffic ขาเข้าสูง
    if data['rxload'] > config['model']['threshold_load']:
        pct = round(data['rxload'] / 255 * 100, 1)
        causes.append(f"Traffic ขาเข้าสูง ({pct}%)")
        suggestions.append("ตรวจสอบ traffic อาจถูก DDoS")

    # ตรวจสอบความเสถียรต่ำ
    if data['reliability'] < config['model']['threshold_reliability']:
        pct = round(data['reliability'] / 255 * 100, 1)
        causes.append(f"ความเสถียรต่ำ ({pct}%)")
        suggestions.append("ตรวจสอบคุณภาพสาย")

    # ตรวจสอบ input errors สูง
    if data['input_errors'] > config['model']['threshold_errors']:
        causes.append(f"Input errors {data['input_errors']} ครั้ง")
        suggestions.append("ตรวจสอบ duplex mismatch หรือสายชำรุด")

    return causes, suggestions

def predict_one(data):
    """ทำนายความผิดปกติสำหรับข้อมูล interface ชุดเดียว"""
    # ถ้าไม่มี AI model ให้ใช้ label จากการตรวจสอบ threshold แทน
    if model is None:
        return data['label'], 1.0

    # จัดรูปแบบข้อมูลสำหรับ AI model
    features = pd.DataFrame([{
        'status_num'   : data['status_num'],
        'protocol_num' : data['protocol_num'],
        'reliability'  : data['reliability'],
        'network_load' : data['network_load'],
        'rxload'       : data['rxload'],
        'input_errors' : data['input_errors']
    }])

    # ทำนายด้วย AI model
    prediction = model.predict(features)[0]
    # คำนวณค่าความมั่นใจของการทำนาย
    confidence = max(model.predict_proba(features)[0])
    return prediction, confidence

def predict_all(collected_data):
    """ทำนายความผิดปกติสำหรับข้อมูล interface ทั้งหมด"""
    anomalies = []  # รายการความผิดปกติที่พบ

    # วนลูปทำนายทีละ interface
    for data in collected_data:
        prediction, confidence = predict_one(data)

        # บันทึกผลการทำนายลงฐานข้อมูล
        save_prediction(
            data['log_id'],
            data['device'],
            data['intf'],
            prediction,
            round(confidence, 4)
        )

        # ถ้าทำนายว่าเป็นความผิดปกติ ให้วิเคราะห์สาเหตุและเพิ่มในรายการ
        if prediction == 'anomaly':
            causes, suggestions = analyze_cause(data)
            anomalies.append({
                **data,
                'prediction'  : prediction,
                'confidence'  : confidence,
                'causes'      : causes,
                'suggestions' : suggestions
            })

    return anomalies