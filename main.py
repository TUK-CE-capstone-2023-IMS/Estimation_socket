import threading
import socket
import struct
import time
from queue import Queue
import datetime
import math

SRS_TARGET_STATUS_STANDING = 0
SRS_TARGET_STATUS_LYING = 1
SRS_TARGET_STATUS_SITTING = 2
SRS_TARGET_STATUS_FALL = 3
SRS_TARGET_STATUS_UNKNOWN = 4

data_queue = Queue()

class SRS_POINT_INFO:
    def __init__(self, data):
        self.posX, self.posY, self.posZ, self.doppler, self.power = struct.unpack('fffff', data)

class SRS_TARGET_INFO:
    def __init__(self, data):
        self.posX, self.posY, self.status, self.id, *self.reserved = struct.unpack('ffIIIfff', data)

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

def sendToUnity(target):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverAddressPort = ("127.0.0.1", 5051)
    id, posX, posY, status, time = target
    message = "{}|{}|{}|{}|{}".format(id, posX, posY, status,time)
    sock.sendto(message.encode(), serverAddressPort)
    print(message)

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
                    current_time_stamp = time.time() 
                    data_queue.put((data, current_time_stamp))

                  

class ProcessThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.running = True
    def run(self):
        while self.running:
            if not data_queue.empty():
                data = data_queue.get()
                send_data = self.parse_data(data)
                if send_data:
                    sendToUnity(send_data)
                data_queue.queue.clear() 
    def parse_data(self, packet):
        data, timestamp = packet  
        if len(data) < 16:
            return None

        current_date_time = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

        offset = 16
        if len(data) < offset + 4:  
            print("데이터 패킷이 너무 짧습니다. 필요한 길이: {}, 현재 길이: {}".format(offset + 4, len(data)))
            return None

        target_num = struct.unpack('I', data[offset:offset+4])[0]
        offset += 4
        for _ in range(target_num):
            if len(data) - offset < 32:  
                break  
            target_data = data[offset:offset+32]
            target = SRS_TARGET_INFO(target_data)
            if(get_status_string(target.status)!="UNKNOWN"):
                if not (math.isclose(target.id, 0, abs_tol=1e-5) or 
                        math.isclose(target.posX, 0, abs_tol=1e-5) or 
                        math.isclose(target.posY, 0, abs_tol=1e-5)):
                    if(target.id < 10 and target.id != 0):
                        offset += 32
                        return [target.id, target.posX, target.posY, get_status_string(target.status), current_date_time]
                offset += 32
            else: 
                offset += 32


        return None



if __name__ == "__main__":
    process_thread = ProcessThread()
    process_thread.start()
    
    capture_thread = CaptureThread()
    capture_thread.start()
