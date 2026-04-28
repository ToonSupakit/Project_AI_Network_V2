# นำเข้าไลบรารีที่จำเป็นสำหรับ Discord Bot
import discord  # ไลบรารีสำหรับสร้าง Discord bot
import yaml  # สำหรับอ่านไฟล์การตั้งค่า
import asyncio  # สำหรับการทำงานแบบ asynchronous
from datetime import datetime  # สำหรับจัดการวันที่และเวลา
from db import get_anomaly_history, get_device_status, mark_as_fixed, get_analytics  # ฟังก์ชันสำหรับจัดการฐานข้อมูล
from netmiko import ConnectHandler  # ไลบรารีสำหรับเชื่อมต่อกับอุปกรณ์เครือข่าย

# อ่านไฟล์การตั้งค่าจาก config.yaml
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# อ่านไฟล์ข้อมูลอุปกรณ์จาก devices.yaml
with open('devices.yaml', 'r', encoding='utf-8') as f:
    devices_config = yaml.safe_load(f)

# กำหนดค่าเริ่มต้นสำหรับ Discord client
intents = discord.Intents.default()
intents.message_content = True  # อนุญาตให้อ่านเนื้อหาข้อความ
intents.messages = True  # อนุญาตให้รับข้อความ
client = discord.Client(intents=intents)

# คิวสำหรับจัดการความผิดปกติที่ต้องแจ้งเตือน
anomaly_queue = asyncio.Queue()

# ดึงค่า threshold จากการตั้งค่า
THRESHOLD_LOAD = config['model']['threshold_load']

# ── ฟังก์ชันสำหรับแจ้งเตือนเมื่อเชื่อมต่อ Timeout ────────────────────────────
async def send_timeout_alert(info):
    """ส่งข้อความแจ้งเตือนไปยัง Discord เมื่อไม่สามารถเชื่อมต่อกับอุปกรณ์ได้"""
    # ดึงข้อมูลช่องที่จะส่งข้อความ
    channel = client.get_channel(config['discord']['channel_id'])
    if not channel:
        return

    # สร้าง embed message สำหรับแจ้งเตือน
    embed = discord.Embed(
        title     = "⚠️ Device Timeout!",
        color     = discord.Color.orange(),
        timestamp = datetime.now()
    )
    embed.add_field(name="Device", value=info['device'],      inline=True)
    embed.add_field(name="Host",   value=info['host'],        inline=True)
    embed.add_field(name="Zone",   value=info['zone'],        inline=True)
    embed.add_field(name="Error",  value=info['error'][:200], inline=False)
    embed.set_footer(text="Python ไม่สามารถเชื่อมต่อได้ กรุณาตรวจสอบ device")
    await channel.send(embed=embed)

# ── ฟังก์ชันค้นหาข้อมูลอุปกรณ์จากชื่อ ───────────────────────────────────
def get_device_by_name(name):
    """ค้นหาข้อมูลอุปกรณ์จากชื่อใน devices.yaml"""
    for d in devices_config['devices']:
        if d['name'] == name:
            return d
    return None

# ── ฟังก์ชันสำหรับแจ้งเตือนความผิดปกติ ────────────────────────────────────
async def send_anomaly_alert(anomaly):
    """ส่งข้อความแจ้งเตือนความผิดปกติไปยัง Discord พร้อมปุ่มจัดการ"""
    # ดึงข้อมูลช่องที่จะส่งข้อความ
    channel = client.get_channel(config['discord']['channel_id'])
    if not channel:
        return

    # จัดรูปแบบข้อความสาเหตุและคำแนะนำ
    causes_text      = "\n".join([f"• {c}" for c in anomaly['causes']])
    suggestions_text = "\n".join([f"• {s}" for s in anomaly['suggestions']])

    # สร้าง embed message สำหรับแจ้งเตือนความผิดปกติ
    embed = discord.Embed(
        title     = "🚨 ANOMALY DETECTED!",
        color     = discord.Color.red(),
        timestamp = datetime.now()
    )
    embed.add_field(name="Device",      value=anomaly['device'],                                                              inline=True)
    embed.add_field(name="Interface",   value=f"{anomaly['intf']} ({anomaly['ip']})",                                         inline=True)
    embed.add_field(name="Link Type",   value=anomaly['link_type'],                                                           inline=True)
    embed.add_field(name="Confidence",  value=f"{anomaly['confidence']:.0%}",                                                 inline=True)
    embed.add_field(name="Status",      value='up' if anomaly['status_num'] else 'down',                                      inline=True)
    embed.add_field(name="Protocol",    value='up' if anomaly['protocol_num'] else 'down',                                    inline=True)
    embed.add_field(name="TX Load",     value=f"{anomaly['network_load']}/255 ({round(anomaly['network_load']/255*100,1)}%)", inline=True)
    embed.add_field(name="RX Load",     value=f"{anomaly['rxload']}/255 ({round(anomaly['rxload']/255*100,1)}%)",             inline=True)
    embed.add_field(name="Reliability", value=f"{anomaly['reliability']}/255",                                                inline=True)
    embed.add_field(name="🔎 สาเหตุ",   value=causes_text   or "ไม่ทราบสาเหตุ",                                           inline=False)
    embed.add_field(name="💡 คำแนะนำ",  value=suggestions_text or "-",                                                        inline=False)

    # สร้างปุ่มจัดการความผิดปกติ
    view = AnomalyView(anomaly)
    await channel.send(embed=embed, view=view)

# ── คลาสสำหรับปุ่มจัดการความผิดปกติ (Fix Now / Check Status / Rate Limit / Ignore) ────
class AnomalyView(discord.ui.View):
    """คลาสสำหรับสร้างปุ่มจัดการความผิดปกติใน Discord"""
    def __init__(self, anomaly):
        super().__init__(timeout=300)  # ปุ่มหายไปหลัง 5 นาที
        self.anomaly = anomaly

    # ── ปุ่ม Fix Now (แก้ไขทันที) ──────────────────────────────────────────
    @discord.ui.button(label="🔧 Fix Now", style=discord.ButtonStyle.danger)
    async def fix_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ปุ่มสำหรับแก้ไขปัญหาความผิดปกติทันทีด้วยคำสั่ง no shutdown"""
        await interaction.response.defer()

        # ค้นหาข้อมูลอุปกรณ์
        device = get_device_by_name(self.anomaly['device'])
        if not device:
            await interaction.followup.send("❌ ไม่พบข้อมูล device")
            return

        await interaction.followup.send(f"⏳ กำลัง fix {self.anomaly['device']} - {self.anomaly['intf']}...")

        try:
            # กำหนดพารามิเตอร์สำหรับเชื่อมต่อ
            conn_params = {
                'device_type': device['device_type'],
                'host'       : device['host'],
                'username'   : device['username'],
                'password'   : device['password'],
                'secret'     : device['secret'],
            }
            # รันคำสั่ง fix ใน background thread
            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: fix_interface(conn_params, self.anomaly['intf'])
            )

            # อัพเดตสถานะเป็น fixed ในฐานข้อมูล
            mark_as_fixed(self.anomaly['log_id'])

            # ส่งข้อความยืนยันการแก้ไขสำเร็จ
            embed = discord.Embed(
                title     = "✅ Fix สำเร็จ!",
                color     = discord.Color.green(),
                timestamp = datetime.now()
            )
            embed.add_field(name="Device",    value=self.anomaly['device'], inline=True)
            embed.add_field(name="Interface", value=self.anomaly['intf'],   inline=True)
            embed.add_field(name="Action",    value="no shutdown",          inline=True)
            embed.add_field(name="Result",    value=result[:500],           inline=False)
            await interaction.followup.send(embed=embed)

            # ปิดปุ่มหลังจากใช้งานแล้ว
            button.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.followup.send(f"❌ Fix ไม่สำเร็จ: {e}")

    # ── ปุ่ม Check Status (ตรวจสอบสถานะ) ─────────────────────────────────────
    @discord.ui.button(label="📊 Check Status", style=discord.ButtonStyle.primary)
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ปุ่มสำหรับตรวจสอบสถานะปัจจุบันของ interface"""
        await interaction.response.defer()

        # ค้นหาข้อมูลอุปกรณ์
        device = get_device_by_name(self.anomaly['device'])
        if not device:
            await interaction.followup.send("❌ ไม่พบข้อมูล device")
            return

        try:
            # กำหนดพารามิเตอร์สำหรับเชื่อมต่อ
            conn_params = {
                'device_type': device['device_type'],
                'host'       : device['host'],
                'username'   : device['username'],
                'password'   : device['password'],
                'secret'     : device['secret'],
            }
            # รันคำสั่งตรวจสอบสถานะใน background thread
            loop   = asyncio.get_event_loop()
            status = await loop.run_in_executor(
                None, lambda: check_interface_status(conn_params, self.anomaly['intf'])
            )

            # ส่งข้อความแสดงสถานะปัจจุบัน
            embed = discord.Embed(
                title     = f"📊 Status: {self.anomaly['device']} - {self.anomaly['intf']}",
                color     = discord.Color.blue(),
                timestamp = datetime.now()
            )
            embed.add_field(name="Current Status", value=status, inline=False)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Check status ไม่สำเร็จ: {e}")

    # ── ปุ่ม Rate Limit (จำกัดความเร็ว) ───────────────────────────────────────
    @discord.ui.button(label="🚦 Rate Limit", style=discord.ButtonStyle.primary)
    async def rate_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ปุ่มสำหรับจำกัดความเร็ว network ที่ 50Mbps"""
        await interaction.response.defer()

        # ตรวจสอบว่าเป็น high traffic หรือไม่
        if self.anomaly['network_load'] <= THRESHOLD_LOAD and self.anomaly['rxload'] <= THRESHOLD_LOAD:
            await interaction.followup.send("ℹ️ Anomaly นี้ไม่ใช่ High Traffic ไม่จำเป็นต้อง Rate Limit")
            return

        # ค้นหาข้อมูลอุปกรณ์
        device = get_device_by_name(self.anomaly['device'])
        if not device:
            await interaction.followup.send("❌ ไม่พบข้อมูล device")
            return

        await interaction.followup.send(f"⏳ กำลัง Rate Limit {self.anomaly['device']} - {self.anomaly['intf']}...")

        try:
            # กำหนดพารามิเตอร์สำหรับเชื่อมต่อ
            conn_params = {
                'device_type': device['device_type'],
                'host'       : device['host'],
                'username'   : device['username'],
                'password'   : device['password'],
                'secret'     : device['secret'],
            }
            # รันคำสั่งจำกัดความเร็วใน background thread
            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: apply_rate_limit(conn_params, self.anomaly['intf'])
            )

            # ส่งข้อความยืนยันการจำกัดความเร็ว
            embed = discord.Embed(
                title     = "🚦 Rate Limit Applied!",
                color     = discord.Color.yellow(),
                timestamp = datetime.now()
            )
            embed.add_field(name="Device",    value=self.anomaly['device'], inline=True)
            embed.add_field(name="Interface", value=self.anomaly['intf'],   inline=True)
            embed.add_field(name="Action",    value="Rate Limit 50Mbps",    inline=True)
            embed.add_field(name="Result",    value=result[:500],           inline=False)
            embed.set_footer(text="⚠️ Rate limit นี้เป็นแค่ชั่วคราว ควรหาสาเหตุที่แท้จริงด้วย")
            await interaction.followup.send(embed=embed)

            # ปิดปุ่มหลังจากใช้งานแล้ว
            button.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.followup.send(f"❌ Rate Limit ไม่สำเร็จ: {e}")

    # ── ปุ่ม Remove Rate Limit (ยกเลิกการจำกัดความเร็ว) ────────────────────────────────
    @discord.ui.button(label="🔓 Remove Limit", style=discord.ButtonStyle.secondary)
    async def remove_rate_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ปุ่มสำหรับยกเลิกการจำกัดความเร็ว"""
        await interaction.response.defer()

        # ค้นหาข้อมูลอุปกรณ์
        device = get_device_by_name(self.anomaly['device'])
        if not device:
            await interaction.followup.send("❌ ไม่พบข้อมูล device")
            return

        try:
            # กำหนดพารามิเตอร์สำหรับเชื่อมต่อ
            conn_params = {
                'device_type': device['device_type'],
                'host'       : device['host'],
                'username'   : device['username'],
                'password'   : device['password'],
                'secret'     : device['secret'],
            }
            # รันคำสั่งยกเลิกการจำกัดความเร็วใน background thread
            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: remove_rate_limit(conn_params, self.anomaly['intf'])
            )

            # ส่งข้อความยืนยันการยกเลิกการจำกัดความเร็ว
            embed = discord.Embed(
                title     = "🔓 Rate Limit Removed!",
                color     = discord.Color.green(),
                timestamp = datetime.now()
            )
            embed.add_field(name="Device",    value=self.anomaly['device'], inline=True)
            embed.add_field(name="Interface", value=self.anomaly['intf'],   inline=True)
            embed.add_field(name="Result",    value=result[:500],           inline=False)
            await interaction.followup.send(embed=embed)

            # ปิดปุ่มหลังจากใช้งานแล้ว
            button.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.followup.send(f"❌ Remove Rate Limit ไม่สำเร็จ: {e}")

    # ── ปุ่ม Ignore (เพิกเฉย) ───────────────────────────────────────────
    @discord.ui.button(label="❌ Ignore", style=discord.ButtonStyle.secondary)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ปุ่มสำหรับเพิกเฉยความผิดปกติ"""
        await interaction.response.send_message(
            f"⏭️ Ignored: {self.anomaly['device']} - {self.anomaly['intf']}"
        )
        # ปิดปุ่มทั้งหมดหลังจากเพิกเฉย
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

# ── ฟังก์ชันสำหรับจัดการอุปกรณ์เครือข่าย (Fix / Check / Rate Limit) ────────────────────
def fix_interface(conn_params, intf):
    """ฟังก์ชันสำหรับแก้ไข interface ด้วยคำสั่ง no shutdown"""
    with ConnectHandler(**conn_params) as net:
        net.enable()
        output = net.send_config_set([
            f"interface {intf}",
            "no shutdown"
        ])
        return output

def check_interface_status(conn_params, intf):
    """ฟังก์ชันสำหรับตรวจสอบสถานะ interface"""
    with ConnectHandler(**conn_params) as net:
        net.enable()
        output = net.send_command(f"show interface {intf}")
        return output[:500]

def apply_rate_limit(conn_params, intf):
    """ฟังก์ชันสำหรับจำกัดความเร็ว network ที่ 50Mbps"""
    with ConnectHandler(**conn_params) as net:
        net.enable()
        output = net.send_config_set([
            f"interface {intf}",
            "rate-limit input  50000000 8000 8000 conform-action transmit exceed-action drop",
            "rate-limit output 50000000 8000 8000 conform-action transmit exceed-action drop"
        ])
        return output

def remove_rate_limit(conn_params, intf):
    """ฟังก์ชันสำหรับยกเลิกการจำกัดความเร็ว"""
    with ConnectHandler(**conn_params) as net:
        net.enable()
        output = net.send_config_set([
            f"interface {intf}",
            "no rate-limit input  50000000 8000 8000 conform-action transmit exceed-action drop",
            "no rate-limit output 50000000 8000 8000 conform-action transmit exceed-action drop"
        ])
        return output

# ── Event Handlers สำหรับ Discord Bot ────────────────────────────────────────────────
@client.event
async def on_ready():
    """ฟังก์ชันที่ทำงานเมื่อ Bot เริ่มต้นพร้อมใช้งาน"""
    print(f"✅ Discord Bot พร้อมใช้งาน: {client.user}")
    # เริ่มต้น process anomaly queue ใน background
    client.loop.create_task(process_anomaly_queue())

@client.event
async def on_message(message):
    """ฟังก์ชันที่ทำงานเมื่อมีข้อความใหม่ใน Discord"""
    # ไม่ตอบสนองข้อความของตัวเอง
    if message.author == client.user:
        return

    # ── คำสั่ง !history (ดูประวัติความผิดปกติ) ─────────────────────────────────
    if message.content.startswith('!history'):
        # ดึงข้อมูลประวัติความผิดปกติ 10 รายการล่าสุด
        rows = get_anomaly_history(limit=10)
        if not rows:
            await message.channel.send("✅ ไม่มี anomaly history")
            return

        # สร้าง embed message สำหรับแสดงประวัติ
        embed = discord.Embed(
            title     = "📋 Anomaly History (10 รายการล่าสุด)",
            color     = discord.Color.orange(),
            timestamp = datetime.now()
        )
        for row in rows:
            status = "✅ Fixed" if row[5] else "🔴 Not Fixed"
            embed.add_field(
                name  = f"{row[1]} - {row[2]}",
                value = f"เวลา: {row[0].strftime('%Y-%m-%d %H:%M:%S')}\nStatus: {status}\nConfidence: {row[4]:.0%}",
                inline = True
            )
        await message.channel.send(embed=embed)

    # ── คำสั่ง !status (ดูสถานะปัจจุบัน) ─────────────────────────────────────
    if message.content.startswith('!status'):
        # ดึงข้อมูลสถานะปัจจุบันของทุกอุปกรณ์
        rows = get_device_status()
        if not rows:
            await message.channel.send("❌ ไม่มีข้อมูล")
            return

        # สร้าง embed message สำหรับแสดงสถานะเครือข่าย
        embed = discord.Embed(
            title     = "📡 Network Status",
            color     = discord.Color.green(),
            timestamp = datetime.now()
        )
        for row in rows:
            label        = row[8]
            status_emoji = "✅" if label == 'normal' else "🚨"
            embed.add_field(
                name   = f"{status_emoji} {row[0]} - {row[1]}",
                value  = f"IP: {row[2]}\nStatus: {row[3]}/{row[4]}\nLoad: {row[5]}/{row[6]}",
                inline = True
            )
        await message.channel.send(embed=embed)

    # ── คำสั่ง !help (แสดงความช่วยเหลือ) ─────────────────────────────────────
    if message.content.startswith('!help'):
        # สร้าง embed message สำหรับแสดงคำสั่งทั้งหมด
        embed = discord.Embed(
            title       = "📖 Commands",
            description = "คำสั่งที่ใช้ได้",
            color       = discord.Color.blue()
        )
        embed.add_field(name="!status",    value="ดู status ทุก interface ตอนนี้",            inline=False)
        embed.add_field(name="!history",   value="ดู anomaly 10 รายการล่าสุด",                inline=False)
        embed.add_field(name="!analytics", value="สรุป anomaly, uptime, fix rate, traffic",  inline=False)
        embed.add_field(name="!help",      value="แสดงคำสั่งทั้งหมด",                         inline=False)
        await message.channel.send(embed=embed)

    # ── คำสั่ง !analytics (ดูสรุปข้อมูลวิเคราะห์) ────────────────────────────────────
    if message.content.startswith('!analytics'):
        # ดึงข้อมูลวิเคราะห์ทั้งหมดจากฐานข้อมูล
        data = get_analytics()

        # ── Embed 1: Overview (ภาพรวม) ────────────────────────────────
        embed1 = discord.Embed(
            title     = "📊 Network Analytics — Overview",
            color     = discord.Color.blurple(),
            timestamp = datetime.now()
        )

        s = data['summary']
        embed1.add_field(name = "📦 Total Records", value = f"{s[0]:,} logs", inline = True)
        embed1.add_field(name = "🚨 Total Anomaly", value = f"{s[1]:,} ({s[3]}%)", inline = True)
        embed1.add_field(name = "✅ Total Normal",  value = f"{s[2]:,}", inline = True)
        embed1.add_field(name = "🗓️ Anomaly Today", value = f"{data['today'][0]:,} cases", inline = True)

        fr = data['fix_rate']
        embed1.add_field(name = "🔧 Fix Rate", value = f"{fr[1]}/{fr[0]} ({fr[2]}%)", inline = True)

        await message.channel.send(embed=embed1)

        # ── Embed 2: Uptime (เวลาทำงาน) ───────────────────────────────────
        embed2 = discord.Embed(
            title = "⏱️ Device Uptime",
            color = discord.Color.green()
        )
        for row in data['uptime']:
            uptime_pct = row[1]
            emoji = "🟢" if uptime_pct >= 99 else "🟡" if uptime_pct >= 95 else "🔴"
            embed2.add_field(
                name  = f"{emoji} {row[0]}",
                value = f"Uptime: **{uptime_pct}%**\nRecords: {row[2]:,}",
                inline = True
            )
        await message.channel.send(embed=embed2)

        # ── Embed 3: Top Devices & Interfaces (อุปกรณ์และ Interface ที่มีปัญหามากสุด) ─────────────────
        embed3 = discord.Embed(
            title = "🏆 Top Problem Devices & Interfaces",
            color = discord.Color.red()
        )

        top_dev_text = "\n".join([f"{i+1}. **{row[0]}** — {row[1]:,} anomalies" for i, row in enumerate(data['top_devices'])]) or "ไม่มีข้อมูล"
        top_intf_text = "\n".join([f"{i+1}. **{row[0]}** {row[1]} — {row[2]:,} anomalies" for i, row in enumerate(data['top_interfaces'])]) or "ไม่มีข้อมูล"

        embed3.add_field(name="📡 Top Devices",    value=top_dev_text,  inline=True)
        embed3.add_field(name="🔌 Top Interfaces", value=top_intf_text, inline=True)
        await message.channel.send(embed=embed3)

        # ── Embed 4: Traffic Trend (แนวโน้มการใช้งาน) ────────────────────────────
        embed4 = discord.Embed(
            title = "📈 Traffic Trend (6 ชั่วโมงล่าสุด)",
            color = discord.Color.orange()
        )

        if data['traffic_trend']:
            trend_text = ""
            for row in data['traffic_trend']:
                load_pct = round(row[1] / 255 * 100, 1)
                max_pct  = round(row[2] / 255 * 100, 1)
                bar = "🔴" if load_pct > 50 else "🟡" if load_pct > 20 else "🟢"
                trend_text += f"{bar} **{row[0]}** — avg {load_pct}% | max {max_pct}%\n"
            embed4.add_field(name="Load per Hour", value=trend_text, inline=False)
        else:
            embed4.add_field(name="Load per Hour", value="ไม่มีข้อมูล", inline=False)

        await message.channel.send(embed=embed4)

        # ── Embed 5: Anomaly by Type (ประเภทของความผิดปกติ) ──────────────────────────
        embed5 = discord.Embed(
            title = "🔍 Anomaly by Type",
            color = discord.Color.dark_red()
        )

        type_text = ""
        for row in data['anomaly_by_type']:
            if row[0] == 'admin_down': emoji = "🔴 Admin Down"
            elif row[0] == 'up' and row[1] == 'down': emoji = "🟠 Protocol Down"
            elif row[0] == 'down': emoji = "⚫ Physical Down"
            else: emoji = "🟡 High Traffic"
            type_text += f"{emoji} — **{row[2]:,}** cases\n"

        embed5.add_field(name = "Breakdown", value = type_text or "ไม่มีข้อมูล", inline = False)
        await message.channel.send(embed=embed5)

# ── ฟังก์ชันสำหรับจัดการคิวความผิดปกติ ─────────────────────────────────
async def process_anomaly_queue():
    """ฟังก์ชันสำหรับประมวลผลคิวความผิดปกติแบบต่อเนื่อง"""
    while True:
        try:
            # รอรับความผิดปกติจากคิว (timeout 1 วินาที)
            anomaly = await asyncio.wait_for(anomaly_queue.get(), timeout=1.0)
            # ส่งการแจ้งเตือนไปยัง Discord
            await send_anomaly_alert(anomaly)
        except asyncio.TimeoutError:
            # ถ้าหมดเวลา ให้ทำงานต่อไป
            continue
        except Exception as e:
            # แสดงข้อผิดพลาดถ้ามีปัญหา
            print(f"❌ Bot error: {e}")

def run_bot():
    """ฟังก์ชันสำหรับเริ่มต้น Discord Bot"""
    client.run(config['discord']['token'])