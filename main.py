import socket
import struct
from queue import Queue
from tensorflow.keras.models import load_model

# 상태 상수
SRS_TARGET_STATUS_STANDING = 0
SRS_TARGET_STATUS_LYING = 1
SRS_TARGET_STATUS_SITTING = 2
SRS_TARGET_STATUS_FALL = 3
SRS_TARGET_STATUS_UNKNOWN = 4

# 데이터 큐
data_queue = Queue()

# 타겟 정보 클래스
class SRS_TARGET_INFO:
    def __init__(self, data):
        self.posX, self.posY, self.status, self.id, *self.reserved = struct.unpack('ffIIIfff', data)

# 상태 문자열 반환 함수
def get_status_string(status):
    if status == SRS_TARGET_STATUS_STANDING:
        return "STANDING"
    elif status == SRS_TARGET_STATUS_LYING:
        return "LYING"
    elif status == SRS_TARGET_STATUS_SITTING:
        return "SITTING"
    elif status == SRS_TARGET_STATUS_FALL:
        return "FALL"
    else:
        return "UNKNOWN"

def capture_data(ip, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 5120000)
        while True:
            header = sock.recv(24)
            if not header or len(header) < 24:
                continue
            packet_size = struct.unpack('I', header[16:20])[0]
            data = sock.recv(packet_size)
            if not data:
                continue
            data_queue.put(data)

def process_data():
    while True:
        if not data_queue.empty():
            data = data_queue.get()
            parse_data(data)

def parse_data(data):
    if data is None or len(data) < 16:
        return
    magic_word = struct.unpack('4H', data[:8])
    frame_count = struct.unpack('I', data[8:12])[0]

    offset = 16
    point_num = struct.unpack('I', data[offset:offset+4])[0]
    offset += 4 + (point_num * 20)  # 포인트 데이터를 건너뜁니다.

    if len(data) - offset >= 4:
        target_num = struct.unpack('I', data[offset:offset+4])[0]
        offset += 4
        for _ in range(target_num):
            if len(data) - offset < 32:
                break
            target_data = data[offset:offset+32]
            target = SRS_TARGET_INFO(target_data)
            print("X:{:.2f}, Y:{:.2f}, Status: {}({})".format(target.posX, target.posY, get_status_string(target.status), target.status))
            offset += 32

if __name__ == "__main__":
    IP = "192.168.30.1"
    PORT = 29172
    capture_data(IP, PORT)
    process_data()
