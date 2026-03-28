import requests
for p in (8000,80):
    url=f'http://192.168.11.108:{p}/api/hardware/nfc/command/poll?device_id=door_controller_2'
    try:
        r=requests.get(url,timeout=4)
        print(p,'OK',r.status_code,r.text[:120])
    except Exception as e:
        print(p,'ERR',type(e).__name__,e)
