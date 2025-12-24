"""创建测试数据：用户、设备、NFC 卡。

此脚本直接使用应用的数据库会话，绕过密码哈希以便在测试环境快速创建用户。
"""
from app.database import SessionLocal, init_db
from app.models import User, HardwareDevice, NFCCard
from datetime import datetime

if __name__ == '__main__':
    init_db()
    db = SessionLocal()
    try:
        # 用户
        user = db.query(User).filter(User.username == 'testuser').first()
        if not user:
            user = User(username='testuser', password_hash='testpass', full_name='测试用户')
            db.add(user)
            db.commit()
            db.refresh(user)
            print('Created user:', user.id)
        else:
            print('User exists:', user.id)

        # 设备
        device = db.query(HardwareDevice).filter(HardwareDevice.device_id == 'nfc_reader_01').first()
        if not device:
            device = HardwareDevice(device_id='nfc_reader_01', device_name='ESP PN532', device_type='nfc_reader', connection_status='offline')
            db.add(device)
            db.commit()
            db.refresh(device)
            print('Created device:', device.device_id)
        else:
            print('Device exists:', device.device_id)

        # 卡片
        card = db.query(NFCCard).filter(NFCCard.card_number == 'CARD123').first()
        if not card:
            card = NFCCard(user_id=user.id, card_number='CARD123', card_name='测试卡', permission_start_date=datetime.utcnow())
            db.add(card)
            db.commit()
            db.refresh(card)
            print('Created card:', card.card_number)
        else:
            print('Card exists:', card.card_number)

    finally:
        db.close()
