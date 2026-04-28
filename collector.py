# นำเข้าไลบรารีที่จำเป็นสำหรับการเก็บข้อมูลจากอุปกรณ์เครือข่าย
from netmiko import ConnectHandler  # ไลบรารีสำหรับเชื่อมต่อกับอุปกรณ์เครือข่าย
from db import save_log  # ฟังก์ชันสำหรับบันทึกข้อมูลลงฐานข้อมูล
import yaml  # สำหรับอ่านไฟล์การตั้งค่า
import re  # สำหรับการประมวลผลข้อความด้วย regular expression
import time  # สำหรับจัดการเวลา

# อ่านไฟล์การตั้งค่าจาก config.yaml
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# อ่านไฟล์ข้อมูลอุปกรณ์จาก devices.yaml
with open('devices.yaml', 'r', encoding='utf-8') as f:
    devices_config = yaml.safe_load(f)

# ดึงค่าการตั้งค่าจากไฟล์ config
SKIP_TYPES            = [s for s in config['anomaly']['skip_types'] if s is not None]  # ประเภท interface ที่จะข้าม
THRESHOLD_LOAD        = config['model']['threshold_load']  # ค่า threshold สำหรับ network load
THRESHOLD_RELIABILITY = config['model']['threshold_reliability']  # ค่า threshold สำหรับ reliability
THRESHOLD_ERRORS      = config['model']['threshold_errors']  # ค่า threshold สำหรับ input errors
MAX_RETRIES           = 3  # จำนวนครั้งสูงสุดในการ retry
RETRY_DELAY           = 5  # ระยะเวลาหน่วงระหว่าง retry (วินาที)

# ── ฟังก์ชันสำหรับกรอง interface ที่ไม่ต้องการตรวจสอบ ─────────────────────────
def should_skip(intf, ip, is_admin_down):
    """ตรวจสอบว่าควรข้าม interface นี้หรือไม่"""
    # ตรวจสอบว่าเป็นประเภทที่ต้องข้ามหรือไม่
    for skip in SKIP_TYPES:
        if intf.startswith(skip):
            return True
    # ข้ามถ้าไม่มี IP และไม่ได้ปิดด้วยคำสั่ง admin
    if ip == 'unassigned' and not is_admin_down:
        return True
    return False

# ── ฟังก์ชันสำหรับกำหนดประเภทการเชื่อมต่อจาก IP ───────────────────────────────
def get_link_type(ip):
    """กำหนดประเภทของการเชื่อมต่อจากช่วง IP"""
    if '192.168.189' in ip:
        return 'Management'  # เครือข่ายจัดการ
    elif ip.startswith('10.10.'):
        return 'Core'  # เครือข่ายหลัก
    elif ip.startswith('192.168.1.') or ip.startswith('192.168.2.'):
        return 'LAN'  # เครือข่ายภายใน
    elif ip == 'unknown':
        return 'Unknown'  # ไม่ทราบ
    else:
        return 'Other'  # อื่นๆ

# ── ฟังก์ชันสำหรับแปลงข้อมูลจากคำสั่ง show interfaces ─────────────────────────────────
def parse_interfaces(raw):
    """แปลงข้อมูลจากคำสั่ง show interfaces เป็นโครงสร้างข้อมูลที่ใช้งานได้"""
    result  = {}
    current = None
    for line in raw.splitlines():
        # หาบรรทัดที่มีข้อมูลสถานะของ interface
        m = re.match(r'^(\S+)\s+is\s+(.+),\s+line protocol is\s+(\S+)', line)
        if m:
            current = m.group(1)
            result[current] = {
                'phys'        : m.group(2).strip(),  # สถานะ physical
                'proto'       : m.group(3).strip(),  # สถานะ protocol
                'reliability' : '255',  # ค่าความเสถียร (default)
                'txload'      : '1',    # ค่า load ขาออก (default)
                'rxload'      : '1',    # ค่า load ขาเข้า (default)
                'input_errors': '0'     # จำนวน input errors (default)
            }
        if current:
            # หาค่า reliability, txload, rxload
            r = re.search(r'reliability (\d+)/255,\s*txload (\d+)/255,\s*rxload (\d+)/255', line)
            if r:
                result[current]['reliability'] = r.group(1)
                result[current]['txload']      = r.group(2)
                result[current]['rxload']      = r.group(3)
            # หาจำนวน input errors
            e = re.search(r'(\d+) input errors', line)
            if e:
                result[current]['input_errors'] = e.group(1)
    return result

# ── ฟังก์ชันสำหรับกำหนด label (ปกติ/ผิดปกติ) ───────────────────────────────────
def get_label(status_num, protocol_num, network_load,
              rxload, reliability, input_errors, is_admin_down):
    """กำหนด label ว่า interface เป็นปกติหรือผิดปกติจากพารามิเตอร์ต่างๆ"""
    # ตรวจสอบสถานะต่างๆ ว่าเป็นความผิดปกติหรือไม่
    if is_admin_down:                        return 'anomaly'  # ถูกปิดด้วยคำสั่ง shutdown
    if status_num   == 0:                    return 'anomaly'  # physical down
    if protocol_num == 0:                    return 'anomaly'  # protocol down
    if network_load > THRESHOLD_LOAD:        return 'anomaly'  # traffic ขาออกสูง
    if rxload       > THRESHOLD_LOAD:        return 'anomaly'  # traffic ขาเข้าสูง
    if reliability  < THRESHOLD_RELIABILITY: return 'anomaly'  # ความเสถียรต่ำ
    if input_errors > THRESHOLD_ERRORS:      return 'anomaly'  # input errors สูง
    return 'normal'  # ถ้าผ่านการตรวจสอบทั้งหมด ถือว่าปกติ

# ── ฟังก์ชันหลักสำหรับเก็บข้อมูลจากอุปกรณ์เดียว ──────────────────────────
def collect_device(device, on_timeout=None):
    """เก็บข้อมูล interface ทั้งหมดจากอุปกรณ์เดียว"""
    for attempt in range(MAX_RETRIES):
        try:
            # กำหนดพารามิเตอร์สำหรับเชื่อมต่อ
            conn_params = {
                'device_type': device['device_type'],
                'host'       : device['host'],
                'username'   : device['username'],
                'password'   : device['password'],
                'secret'     : device['secret'],
            }

            results = []

            # เชื่อมต่อกับอุปกรณ์และเก็บข้อมูล
            with ConnectHandler(**conn_params) as net:
                net.enable()

                # ดึงข้อมูล IP address ของทุก interface
                br_out = net.send_command('show ip int br')
                ip_map = {}
                for line in br_out.splitlines():
                    # ข้ามบรรทัดที่ไม่ใช่ข้อมูล interface
                    if 'Interface' in line or 'OK?' in line or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) < 6:
                        continue
                    ip_map[parts[0]] = parts[1]

                # ดึงข้อมูลรายละเอียดของ interface ทั้งหมดทีเดียว
                detail_out = net.send_command('show interfaces')
                detail_map = parse_interfaces(detail_out)

                # ประมวลผลข้อมูลแต่ละ interface
                for intf, data in detail_map.items():
                    ip            = ip_map.get(intf, 'unassigned')
                    is_admin_down = 'admin' in data['phys'].lower()

                    # ตรวจสอบว่าควรข้าม interface นี้หรือไม่
                    if should_skip(intf, ip, is_admin_down):
                        continue

                    # กำหนดค่า IP สำหรับ interface ที่ถูกปิดด้วย admin
                    if ip == 'unassigned' and is_admin_down:
                        ip = 'unknown'

                    # กำหนดสถานะเป็นตัวเลข
                    if is_admin_down:
                        status_num   = 0
                        protocol_num = 0
                    else:
                        status_num   = 1 if 'up' in data['phys'] else 0
                        protocol_num = 1 if data['proto'] == 'up' else 0

                    # แปลงค่าต่างๆ เป็นตัวเลข
                    reliability  = int(data['reliability'])
                    network_load = int(data['txload'])
                    rxload       = int(data['rxload'])
                    input_errors = int(data['input_errors'])
                    link_type    = get_link_type(ip)
                    label        = get_label(
                        status_num, protocol_num,
                        network_load, rxload,
                        reliability, input_errors,
                        is_admin_down
                    )

                    # บันทึกข้อมูลลงฐานข้อมูล
                    log_id = save_log(
                        device['name'], intf, ip,
                        'admin_down' if is_admin_down else ('up' if status_num else 'down'),
                        'up' if protocol_num else 'down',
                        reliability, network_load, rxload, input_errors,
                        link_type,
                        device.get('zone', 'Unknown'),
                        device.get('location', 'Unknown'),
                        label
                    )

                    # เก็บข้อมูลไว้ส่งกลับ
                    results.append({
                        'log_id'       : log_id,
                        'device'       : device['name'],
                        'intf'         : intf,
                        'ip'           : ip,
                        'status_num'   : status_num,
                        'protocol_num' : protocol_num,
                        'reliability'  : reliability,
                        'network_load' : network_load,
                        'rxload'       : rxload,
                        'input_errors' : input_errors,
                        'link_type'    : link_type,
                        'label'        : label,
                        'is_admin_down': is_admin_down
                    })

            print(f"✅ {device['name']}: เก็บได้ {len(results)} interface")
            return results

        except Exception as e:
            # จัดการการ retry ถ้าเชื่อมต่อล้มเหลว
            if attempt < MAX_RETRIES - 1:
                print(f"⚠️  {device['name']} retry {attempt+1}/{MAX_RETRIES}: {e}")
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ {device['name']}: หมด retry แล้ว — {e}")
                # แจ้งเตือน timeout ถ้ามีฟังก์ชัน callback
                if on_timeout:
                    on_timeout({
                        'device': device['name'],
                        'host'  : device['host'],
                        'zone'  : device.get('zone', 'Unknown'),
                        'error' : str(e)
                    })

    return []

# ── ฟังก์ชันสำหรับเก็บข้อมูลจากอุปกรณ์ทั้งหมด ──────────────────────────────────
def collect_all(on_timeout=None):
    """เก็บข้อมูล interface ทั้งหมดจากอุปกรณ์ทุกตัวใน devices.yaml"""
    all_results = []
    # วนลูปเก็บข้อมูลจากทุกอุปกรณ์
    for device in devices_config['devices']:
        results = collect_device(device, on_timeout=on_timeout)
        all_results.extend(results)
    return all_results