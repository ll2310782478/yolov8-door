import os, signal
pid=46508
try:
    os.kill(pid, signal.SIGTERM)
    print('SIGTERM_SENT', pid)
except Exception as e:
    print('ERR', type(e).__name__, e)
