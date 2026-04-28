# นำเข้าไลบรารีที่จำเป็นสำหรับการทำงาน
import asyncio  # สำหรับการทำงานแบบ asynchronous
import threading  # สำหรับการทำงานแบบมีหลาย thread
import time  # สำหรับจัดการเวลา
import yaml  # สำหรับอ่านไฟล์การตั้งค่า
from db import init_db  # ฟังก์ชันสำหรับเริ่มต้นฐานข้อมูล
from collector import collect_all  # ฟังก์ชันสำหรับเก็บข้อมูลจากอุปกรณ์ทั้งหมด
from predictor import predict_all  # ฟังก์ชันสำหรับทำนายความผิดปกติด้วย AI
from bot import run_bot, anomaly_queue, client, send_timeout_alert  # ฟังก์ชันสำหรับรัน Discord bot



# อ่านไฟล์การตั้งค่าจาก config.yaml
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# ดึงค่าช่วงเวลาจากการตั้งค่า (วินาที)
INTERVAL = config['collector']['interval']

# ── ฟังก์ชันหลักสำหรับเก็บข้อมูลและทำนายความผิดปกติ ────────────────────────
def collect_and_predict():
    """ฟังก์ชันนี้ทำงานในลูปไม่รู้จบ เพื่อเก็บข้อมูลและตรวจจับความผิดปกติ"""
    print("👀 เริ่มเก็บข้อมูลและ predict...")
    while True:
        try:
            # ฟังก์ชันสำหรับจัดการเมื่อเชื่อมต่อ timeout
            def on_timeout(info):
                asyncio.run_coroutine_threadsafe(
                    send_timeout_alert(info),
                    client.loop
                )

            # เก็บข้อมูลจากอุปกรณ์ทั้งหมด
            collected = collect_all(on_timeout=on_timeout)
            # ทำนายความผิดปกติด้วย AI
            anomalies = predict_all(collected)

            # ถ้าพบความผิดปกติ ให้ส่งไปยัง Discord
            if anomalies:
                for anomaly in anomalies:
                    asyncio.run_coroutine_threadsafe(
                        anomaly_queue.put(anomaly),
                        client.loop
                    )
                print(f"🚨 พบ anomaly {len(anomalies)} รายการ")
            else:
                # แสดงสถานะปกติถ้าไม่พบปัญหา
                print(f"✅ [{time.strftime('%H:%M:%S')}] ทุก interface ปกติ")

        except Exception as e:
            # แสดงข้อผิดพลาดถ้ามีปัญหา
            print(f"❌ Collect/Predict error: {e}")

        # รอตามช่วงเวลาที่กำหนดก่อนเริ่มรอบใหม่
        time.sleep(INTERVAL)

# ── ฟังก์ชันหลักของโปรแกรม ──────────────────────────────────────────────────
if __name__ == '__main__':
    """จุดเริ่มต้นการทำงานของโปรแกรม"""
    # แสดงหัวข้อโปรแกรม
    print("="*50)
    print("  Network AI Monitor v2")
    print("="*50)

    # เริ่มต้นฐานข้อมูล
    init_db()

    # รันฟังก์ชันเก็บข้อมูลและทำนายใน background thread
    # เพื่อให้ทำงานพร้อมกับ Discord bot
    t = threading.Thread(target=collect_and_predict, daemon=True)
    t.start()

    # รัน Discord Bot ใน main thread (หลัก)
    print("🤖 เริ่ม Discord Bot...")
    run_bot()