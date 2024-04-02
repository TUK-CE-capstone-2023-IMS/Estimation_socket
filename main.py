import threading
import socket
import struct
import numpy as np
import time
from queue import Queue

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
def sendToUnity(targets):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverAddressPort = ("127.0.0.1", 5051)
    for target in targets:
        if len(target) == 3: 
            posX, posY, status = target
            message = "{}|{}|{}".format(posX, posY, status)
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
                if not data:
                    continue
                data_queue.put(data)

class ProcessThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.running = True
        self.pipe = None
        self.timeSinceCheckedConnection = 0
        self.timeSincePostStatistics = 0

    def run(self):
        capture_thread = CaptureThread()
        capture_thread.start()
        while self.running:
            if not data_queue.empty():
                data = data_queue.get()
                self.parse_data(data)
   
    def parse_data(self, data):
        if data is None:
            return [], []
        if len(data) < 16:
            return [], []
        magic_word = struct.unpack('4H', data[:8])
        frame_count = struct.unpack('I', data[8:12])[0]

        targets = []

        offset = 16
        point_num = struct.unpack('I', data[offset:offset+4])[0]
        # offset += 4 + (point_num * 20)  

        if len(data) - offset >= 4:
            target_num = struct.unpack('I', data[offset:offset+4])[0]
            offset += 4
            send_data = []
            for _ in range(target_num):
                if len(data) - offset < 32:  
                    break  
                target_data = data[offset:offset+32]
                target = SRS_TARGET_INFO(target_data)
                targets.append([target.posX, target.posY, target.status])
                #print("X:{:.2f}, Y:{:.2f}, Status: {}({})".format(target.posX, target.posY, get_status_string(target.status), target.status))
                offset += 32
                send_data.append([target.posX, target.posY, get_status_string(target.status)])
                sendToUnity(send_data)
                send_data.clear
        return targets




if __name__ == "__main__":
    process_thread = ProcessThread()
    process_thread.start()