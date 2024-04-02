import threading
import socket
import struct
import time
from queue import Queue
import datetime
# 상태 정의
SRS_TARGET_STATUS_STANDING = 0
SRS_TARGET_STATUS_LYING = 1
SRS_TARGET_STATUS_SITTING = 2
SRS_TARGET_STATUS_FALL = 3
SRS_TARGET_STATUS_UNKNOWN = 4

# 데이터 큐 생성
data_queue = Queue()

# 포인트 정보 클래스
class SRS_POINT_INFO:
    def __init__(self, data):
        self.posX, self.posY, self.posZ, self.doppler, self.power = struct.unpack('fffff', data)

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
# 유니티에 데이터 전송 함수
def sendToUnity(target):
   
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverAddressPort = ("127.0.0.1", 5051)
    id, posX, posY, status, time = target
    message = "{}|{}|{}|{}|{}".format(id, posX, posY, status,time)
    sock.sendto(message.encode(), serverAddressPort)
    print(message)

# 캡처 스레드
class CaptureThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.ip = "192.168.30.1"
        self.port = 29172
        self.isRunning = True
    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((self.ip, self.port))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 5120000)
            while self.isRunning:
                header = sock.recv(24)
                if not header or len(header) < 24:
                    continue
                packet_size = struct.unpack('I', header[16:20])[0]
                data = sock.recv(packet_size)
                if data:
                    current_time_stamp = time.time()  # 패킷을 읽은 현재 시간
                    data_queue.put((data, current_time_stamp))  # 데이터와 함께 시간을 큐에 추가

# 처리 스레드
class ProcessThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.running = True

    def run(self):
        last_sent_time = time.time()
        while self.running:
            if not data_queue.empty():
                current_time = time.time()
                if current_time - last_sent_time >= 1:  # 1초마다 데이터 전송
                    data = data_queue.get()
                    send_data = self.parse_data(data)
                    if send_data:
                        sendToUnity(send_data)
                        last_sent_time = current_time
                    data_queue.queue.clear()  # 큐 초기화
    def parse_data(self, packet):
        data, timestamp = packet  # 패킷 데이터와 타임스탬프 추출
        if len(data) < 16:
            return None

        current_date_time = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

        offset = 16
        target_num = struct.unpack('I', data[offset:offset+4])[0]
        offset += 4

        for _ in range(target_num):
            if len(data) - offset < 32:
                break
            target_data = data[offset:offset+32]
            target = SRS_TARGET_INFO(target_data)
            if(target.id<100 and target.id!=0):
                offset += 32
                return [target.id, target.posX, target.posY, get_status_string(target.status), current_date_time]
            else: offset += 32
        return None


if __name__ == "__main__":
    process_thread = ProcessThread()
    process_thread.start()

    capture_thread = CaptureThread()
    capture_thread.start()
