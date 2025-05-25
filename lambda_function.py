import json
import os
import boto3
import uuid
from datetime import datetime, timedelta, timezone
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage

s3 = boto3.client('s3')
S3_BUCKET = 'missingpersonsbucket'

dynamodb = boto3.resource('dynamodb')
missing_table = dynamodb.Table('MissingPersons')
found_table = dynamodb.Table('FoundPersons')
temp_table = dynamodb.Table('UserReports')

line_bot_api = LineBotApi(os.environ['YOUR_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['YOUR_CHANNEL_SECRET'])

MISSING_STEPS = [
    {"key": "name_full", "prompt": "เริ่มจากข้อมูลผู้สูญหายนะครับ กรุณาระบุชื่อ-สกุล, ชื่อ-สกุลเดิม (ถ้ามี), ชื่อเล่น\n\tเช่น สมชาย ชัยชนะ, ธนพล ชัยชนะ, ชาย"},
    {"key": "gender_birth", "prompt": "ต่อไปขอข้อมูลเพิ่มเติมครับ/ค่ะ\nเพศ และ วันเกิด ของบุคคลสูญหาย\n\tเช่น ชาย , 25/05/2001"},
    {"key": "disease", "prompt": "บุคคลที่หายมี โรคประจำตัว หอบหืด เบาหวาน หรือไม่ครับ/ค่ะ ?\nหากมี รบกวนระบุ\n\tเช่น หอบหืด"},
    {"key": "disability", "prompt": "มี อาการทางประสาท, หลงลืม หรือไม่\n\tเช่น ระบุว่า อาการทางประสาท หลงลืม\nหรือ\nมีความพิการ อื่น ๆ ใดหรือไม่ครับ?\nถ้ามี รบกวนระบุเพิ่มเติม\n\tเช่น เดินไม่สะดวก หลงลืมง่าย ฯลฯ"},
    {"key": "appearance", "prompt": "ขอลักษณะรูปพรรณสัณฐานภายนอกที่จำเป็นด้วยครับ\nสีผิว (ขาว ,ดำ, ขาว-เหลือง, ดำ-แดง)\nส่วนสูง (ซม.)\nน้ำหนัก (กก.)\n\tสีผิว, ส่วนสูง, น้ำหนัก\n\tเช่น ขาว, 191, 55"},
    {"key": "detail", "prompt": "หากมี รายละเอียดเพิ่มเติม นอกเหนือจากนี้\n\tเช่น จุดสังเกต เสื้อผ้า พฤติกรรม ฯลฯ กรุณาระบุ"},
    {"key": "photo", "prompt": "รบกวนแนบ รูปภาพล่าสุด กรุณาส่งเข้ามาเลยครับ (พิมพ์ข้อความและแนบรูปภาพเพิ่มเติม)\n\tเช่น (ส่งรูปภาพแนบใน LINE)\n\tถ้าไม่มีรูปให้ตอบว่า ไม่มี"},
    {"key": "disappear_place_type", "prompt": "ขอจุดที่หายตัวไป\n1.บ้าน 2.ที่ทำงาน 3.ระหว่างการเดินทาง\n(พิมพ์เลขข้อที่ตรงกับจุดที่หายไป)\n\tเช่น 2"},
    {"key": "disappear_address", "prompt": "ต่อไปขอข้อมูลสถานที่หายตัวไป\nกรุณาระบุ\nที่อยู่\nบ้านเลขที่\nหมู่บ้าน/หมู่บ้านจัดสรร\nถนน/ซอย\nตำบล อำเภอ จังหวัด\n\tเช่น มหาวิทยาลัยธรรมศาสตร์ ท่าพระจันทร์ 2 ถนนพระจันทร์ แขวงพระบรมมหาราชวัง เขตพระนคร กรุงเทพฯ 10200"},
    {"key": "disappear_datetime", "prompt": "📆 วันที่และ ⏰ เวลาที่หายตัวไปคือเมื่อไร?\n\tเช่น 25/5/2025 10:10 น."},
    {"key": "suspected_reason", "prompt": "สาเหตุที่คาดว่าอาจเกี่ยวข้องกับการหายตัวไปคืออะไร\n(พิมพ์เลขข้อที่ตรงกับสถานการณ์)\n\tเช่น 1, 4, 5\n1. มีปากเสียง / ทะเลาะวิวาท\n2. ถูกล่อลวง\n3. หลงลืม / อาการทางประสาท\n4. พลัดหลง / ถูกลักพาตัว\n5. หายโดยสมัครใจ\n6. ไม่ทราบสาเหตุ"},
    {"key": "reporter_info", "prompt": "ต่อไปคือข้อมูลของคุณผู้แจ้งนะคะ\nกรุณาระบุ\nชื่อ\nความสัมพันธ์กับผู้ที่หาย\nเบอร์โทรศัพท์\nอีเมล\n\tเช่น นาย งงงวย นะราช  เป็นพี่ชาย 0987654321 ngong@gmail.com"},
    {"key": "has_report_copy", "prompt": "คุณมี สำเนาใบแจ้งความ หรือไม่คะ? (มี / ไม่มี)\n\tเช่น ตอบ ไม่มี"},
    {"key": "police_info", "prompt": "ขอข้อมูลรายละเอียดเพิ่มเติมจากการแจ้งความค่ะ\nกรุณาระบุ\n-ชื่อสถานีตำรวจ\n-ชื่อเจ้าหน้าที่ตำรวจ\n-วันที่แจ้งความ\n-เบอร์ติดต่อของสถานีตำรวจ\n\tเช่น สถานีตำรวจภูธรอำเภอคลองหลวง\n\tเจ้าหน้าที่ พล.ต.อ. วาสนา ดีเกินคาด\n\t25/5/2025\n\t0123456789\n\tถ้า ไม่ได้แจ้ง/ไม่มีสำเนาแจ้งความ พิมพ์ ไม่มี"},
]

CLUE_STEPS = [
    {"key": "found_person_name", "prompt": "เริ่มจากชื่อของผู้ที่คุณพบเห็นนะครับ\n📌 กรุณาระบุ ชื่อ-สกุล (ถ้าทราบ)\n\tเช่น สมชาย นะราช"},
    {"key": "found_person_desc", "prompt": "กรุณาระบุ ลักษณะหรือรายละเอียดของบุคคลที่คุณพบเห็น\n\tเช่น เพศ, อายุโดยประมาณ, เสื้อผ้า, ลักษณะพิเศษ, พฤติกรรม ฯลฯ"},
    {"key": "found_location", "prompt": "กรุณาระบุ สถานที่ที่คุณพบเห็น บุคคลนั้น\n\tเช่น บริเวณใกล้ตลาด, ถนน, ป้ายรถเมล์, ร้านค้า ฯลฯ"},
    {"key": "found_datetime", "prompt": "📆 กรุณาระบุ วันที่ และ ⏰ เวลาที่พบเห็น\n\tเช่น 25/5/2025 10:10 น."},
    {"key": "found_picture", "prompt": "หากคุณมี รูปถ่ายของบุคคลที่พบเห็น กรุณาแนบรูปเข้ามาได้เลยนะครับ\n(หากไม่มีสามารถพิมพ์ว่า 'ไม่มีรูป')"},
    {"key": "reporter_contact", "prompt": "ขอบคุณที่ช่วยแจ้งเบาะแสครับ 🙏\nกรุณาระบุ ชื่อของคุณ และ เบอร์โทรศัพท์ สำหรับติดต่อกลับ"},
    {"key": "additional_note", "prompt": "คุณมี ข้อสังเกตหรือข้อมูลเพิ่มเติม ที่อยากแจ้งไหมครับ?\nเช่น ดูเหมือนหลงทาง, พูดไม่รู้เรื่อง, มีบาดแผล, หรือเดินวนไปมา ฯลฯ"},
]

SCENARIOS = {
    "missing": MISSING_STEPS,
    "clue": CLUE_STEPS
}

DISAPPEAR_PLACE_MAP = {
    "1": "บ้าน",
    "2": "ที่ทำงาน",
    "3": "ระหว่างการเดินทาง"
}

SUSPECTED_REASON_MAP = {
    "1": "มีปากเสียง / ทะเลาะวิวาท",
    "2": "ถูกล่อลวง",
    "3": "หลงลืม / อาการทางประสาท",
    "4": "พลัดหลง / ถูกลักพาตัว",
    "5": "หายโดยสมัครใจ",
    "6": "ไม่ทราบสาเหตุ"
}

def lambda_handler(event, context):
    print("🚀 เริ่มทำงาน lambda_handler")
    msg = json.loads(event['body'])
    user_id = msg['events'][0]['source']['userId']
    reply_token = msg['events'][0]['replyToken']
    message = msg['events'][0]['message']
    message_type = message['type']
    now = datetime.now(timezone.utc)

    user_data = get_user_data(user_id)

    if message_type == "text":
        user_message = message['text']
        if user_message == "แจ้งคนหาย":
            return start_scenario(user_id, reply_token, now, "missing")
        elif user_message == "แจ้งเบาะแส":
            return start_scenario(user_id, reply_token, now, "clue")
    elif message_type == "image":
        user_message = "[IMAGE]"
    else:
        send_reply(reply_token, "ขออภัย ยังไม่รองรับข้อความประเภทนี้")
        return response_ok()

    if not user_data or "scenario" not in user_data:
        send_reply(reply_token, "กรุณาพิมพ์ 'แจ้งคนหาย' หรือ 'แจ้งเบาะแส' เพื่อเริ่มต้น")
        return response_ok()

    last_time = datetime.fromisoformat(user_data["last_update_time"])
    if now - last_time > timedelta(minutes=5):
        delete_user_data(user_id)
        send_reply(reply_token, "⛔️ เกิน 5 นาที กรุณาเริ่มใหม่อีกครั้ง")
        return response_ok()

    scenario = user_data["scenario"]
    steps = SCENARIOS[scenario]
    state = int(user_data["state"])
    key = steps[state]["key"]
    conversation = user_data.get("conversation", {})

    if message_type == "image":
        try:
            message_id = message['id']
            image_content = line_bot_api.get_message_content(message_id)
            image_data = image_content.content

            filename = f"{str(uuid.uuid4())}.jpg"
            s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=image_data, ContentType='image/jpeg')

            image_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"

            conversation[key] = image_url
        except Exception as e:
            print(f"📸 error loading image: {e}")
            send_reply(reply_token, "เกิดข้อผิดพลาดในการรับรูปภาพ กรุณาลองใหม่ครับ")
            return response_ok()
    else:
        if key == "disappear_place_type":
            conversation[key] = map_disappear_place(user_message)
        elif key == "suspected_reason":
            conversation[key] = map_suspected_reasons(user_message)
        else:
            conversation[key] = user_message

    next_state = state + 1

    if scenario == "missing" and key == "has_report_copy":
        if user_message.strip().lower() in ["ไม่มี", "no", "ไม่มีค่ะ", "ไม่มีครับ"]:
            next_state += 1

    if next_state < len(steps):
        update_user_data(user_id, {
            "user_id": user_id,
            "scenario": scenario,
            "state": next_state,
            "last_update_time": now.isoformat(),
            "conversation": conversation
        })
        send_reply(reply_token, steps[next_state]["prompt"])
    else:
        if scenario == "missing":
            write_to_missing_table(conversation)
        else:
            write_to_found_table(conversation)

        delete_user_data(user_id)
        send_reply(reply_token, "🎉 ขอบคุณครับ/ค่ะ ได้รับข้อมูลของคุณเรียบร้อยแล้ว\nทีมงานจะดำเนินการตรวจสอบและติดต่อกลับหากมีความคืบหน้า\nหากต้องการแจ้งข้อมูลเพิ่มเติม พิมพ์ข้อความเข้ามาได้ตลอดเลยนะ 🙏")

    return response_ok()

def start_scenario(user_id, reply_token, now, scenario):
    update_user_data(user_id, {
        "user_id": user_id,
        "scenario": scenario,
        "state": 0,
        "last_update_time": now.isoformat(),
        "conversation": {}
    })
    send_reply(reply_token, SCENARIOS[scenario][0]["prompt"])
    return response_ok()

def get_user_data(user_id):
    try:
        res = temp_table.get_item(Key={'user_id': user_id})
        return res.get('Item')
    except Exception as e:
        print(f"get_user_data error: {e}")
        return None

def update_user_data(user_id, updates):
    try:
        temp_table.put_item(Item=updates)
    except Exception as e:
        print(f"update_user_data error: {e}")

def delete_user_data(user_id):
    try:
        temp_table.delete_item(Key={'user_id': user_id})
    except Exception as e:
        print(f"delete_user_data error: {e}")

def send_reply(token, text):
    try:
        line_bot_api.reply_message(token, TextSendMessage(text=text))
    except Exception as e:
        print(f"send_reply error: {e}")

def response_ok():
    return {"statusCode": 200, "body": json.dumps({"message": "ok"})}

def write_to_missing_table(convo):
    try:
        print("📥 [Debug] เตรียมบันทึกข้อมูลลง MissingPersons")
        name_parts = convo.get("name_full", "").split(",")
        appearance = convo.get("appearance", "").split(",")
        gender_birth = convo.get("gender_birth", "").split(",")

        item = {
            "person_id": str(uuid.uuid4()),
            "name": name_parts[0].strip() if len(name_parts) > 0 else "",
            "old_name": name_parts[1].strip() if len(name_parts) > 1 else "",
            "nickname": name_parts[2].strip() if len(name_parts) > 2 else "",
            "sex": gender_birth[0].strip() if len(gender_birth) > 0 else "",
            "birthdate": gender_birth[1].strip() if len(gender_birth) > 1 else "",
            "congenital_disease": convo.get("disease", ""),
            "disability": convo.get("disability", ""),
            "skin_color": appearance[0].strip() if len(appearance) > 0 else "",
            "height": appearance[1].strip() if len(appearance) > 1 else "",
            "weight": appearance[2].strip() if len(appearance) > 2 else "",
            "detail": convo.get("detail", ""),
            "photo": convo.get("photo", ""),
            "disappear_location": convo.get("disappear_place_type", ""),
            "address": convo.get("disappear_address", ""),
            "date_time": convo.get("disappear_datetime", ""),
            "cause": convo.get("suspected_reason", ""),
            "reporter_info": convo.get("reporter_info", ""),
            "police_info": convo.get("police_info", "")
        }

        print("📝 [Debug] ข้อมูลที่จะเขียนลง DynamoDB:\n", json.dumps(item, indent=2, ensure_ascii=False))
        response = missing_table.put_item(Item=item)
        print("🛠️ DynamoDB Response:", response)
        missing_table.put_item(Item=item)
        print("✅ [Success] บันทึกข้อมูลสำเร็จ")

    except Exception as e:
        print(f"❌ [Error] write_to_missing_table error: {e}")

def write_to_found_table(convo):
    try:
        found_table.put_item(Item={
            "person_id": str(uuid.uuid4()),
            "found_name": convo.get("found_person_name", ""),
            "found_description": convo.get("found_person_desc", ""),
            "found_location": convo.get("found_location", ""),
            "found_datetime": convo.get("found_datetime", ""),
            "found_picture": convo.get("found_picture", ""),
            "found_reporter_info": convo.get("reporter_contact", ""),
            "found_note": convo.get("additional_note", "")
        })
        print("📥 เข้าฟังก์ชัน write_to_found_table แล้ว")
    except Exception as e:
        print(f"write_to_found_table error: {e}")

def map_disappear_place(value):
    return DISAPPEAR_PLACE_MAP.get(value.strip(), value.strip())

def map_suspected_reasons(value):
    return ", ".join([SUSPECTED_REASON_MAP.get(v.strip(), v.strip()) for v in value.split(",")])