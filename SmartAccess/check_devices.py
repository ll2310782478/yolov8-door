from app.database import SessionLocal
from app.models import HardwareDevice

db = SessionLocal()
devices = db.query(HardwareDevice).all()
print(f"Total devices: {len(devices)}")
for d in devices:
    print(f"ID: {d.device_id}, Name: {d.device_name}, Type: {d.device_type}, Status: {d.connection_status}")
db.close()
