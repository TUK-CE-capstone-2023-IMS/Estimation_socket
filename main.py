import socket
import struct
import requests
# Define constants
SRS_SERVER_PORT = 29172
SRS_MAX_POINT = 2000
SRS_MAX_TARGET = 250



# Ip address
sourceIp = "192.168.0.13"

SRS_TARGET_STATUS_WALKING = 0
SRS_TARGET_STATUS_LYING = 1
SRS_TARGET_STATUS_SITTING = 2
SRS_TARGET_STATUS_FALL = 3
SRS_TARGET_STATUS_UNKNOWN = 4
magic_word_bytes = struct.pack('HHHH', 0x0201, 0x0403, 0x0605, 0x0807)

# Point information structure
class SRS_POINT_INFO:
    def __init__(self, posX=0.0, posY=0.0, posZ=0.0, doppler=0.0, power=0.0):
        self.posX = posX
        self.posY = posY
        self.posZ = posZ
        self.doppler = doppler
        self.power = power

# Target information structure
class SRS_TARGET_INFO:
    def __init__(self, posX=0.0, posY=0.0, status=SRS_TARGET_STATUS_UNKNOWN, id=0, reserved=[0.0, 0.0, 0.0]):
        self.posX = posX
        self.posY = posY
        self.status = status
        self.id = id
        self.reserved = reserved
def memset(buffer, value, size):
    for i in range(size):
        buffer[i] = value

def read_packet(sock, packet_buffer, size_of_buffer):
    read_num = 0
    magic_number = 0xABCD4321
    # 버퍼 초기화
    packet_buffer[:] = bytes([0] * size_of_buffer)

    # 헤더 읽기
    header = sock.recv(36)
    if len(header) != 36:
        return -1

    # 패킷 넘버 읽기
    packet_number_bytes = header[4:8]
    packet_number = struct.unpack('I', packet_number_bytes)[0]

    # 패킷 넘버 확인
    if packet_number != magic_number:
        return 0

    # 데이터 블록 사이즈 읽기
    packet_size_bytes = header[16:20]
    packet_size = struct.unpack('I', packet_size_bytes)[0]

    packet_read = 0

    # 데이터 블록 읽기
    while packet_read < packet_size:
        received_data = sock.recv(packet_size - packet_read)
        if len(received_data) <= 0:
            return -1
        packet_buffer[packet_read:packet_read+len(received_data)] = received_data
        packet_read += len(received_data)

    return packet_size

def sendToUnity(id, posX, posY, status):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverAddressPort = ("127.0.0.1", 5051)
    message = "{}|{}|{}|{}|{}".format(id, posX, posY, status,0)
    sock.sendto(message.encode(), serverAddressPort)
    print(message)

def send_status_to_server(status):
    url = "http://localhost:8080/status"
    data = {"state": status}
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print("Status successfully sent to server.")
        else:
            print("Failed to send status to server. Status code:", response.status_code)
    except Exception as e:
        print("An error occurred while sending status to server:", e)

def main():
    packet_buffer = bytearray(512000)
    buffer_idx = 0
    packet_size = 0
    magic_word = struct.pack('HHHH', 0x0201, 0x0403, 0x0605, 0x0807)
    frame_count = 0
    point_num = 0
    point = [None] * SRS_MAX_POINT
    target_id_per_point = bytearray(SRS_MAX_POINT)

    has_target = 0
    target_num = 0
    target = [None] * SRS_MAX_TARGET
    step = 0


    # 소켓 초기화
    sock = None

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Connecting to {}...".format(sourceIp))
        serveraddr = (sourceIp, SRS_SERVER_PORT)  
        sock.connect(serveraddr)
        print("Connected.")
    except Exception as e:
        print("Connection failed:", e)

    while True:
        has_target = 0
        #print(len(packet_buffer))
        packet_buffer = bytearray(512000)  
        packet_size = read_packet(sock, packet_buffer,len(packet_buffer))
        #print(packet_size,len(packet_buffer))
        if packet_size < 0:
            print("Connection closed.")
            break
        elif packet_size == 0:
            continue

        buffer_idx = 0

        # Parsing data block

        #print(packet_buffer[buffer_idx : buffer_idx + len(magic_word)])
        #print(magic_word_bytes)
        if packet_buffer[buffer_idx : buffer_idx + len(magic_word)] != magic_word_bytes:
            print("Invalid magic word.")
            break

        buffer_idx += len(magic_word)
     
        frame_count = struct.unpack_from('I', packet_buffer, buffer_idx)[0]
        buffer_idx += 4

        point_num = struct.unpack_from('I', packet_buffer, buffer_idx)[0]
        buffer_idx += 4

        #포인트 클라우드 데이터 부분
        for step in range(point_num):
            #point[step] = SRS_POINT_INFO(*struct.unpack_from('fffff', packet_buffer, buffer_idx))
            buffer_idx += 20

        if packet_buffer[buffer_idx : buffer_idx + len(magic_word)] == magic_word:
            has_target = 1
        elif packet_size > 48020 and packet_buffer[48020 : 48020 + len(magic_word)] == magic_word:
            has_target = 2

 
        if has_target:
            for step in range(point_num):
                target_id_per_point[step] = packet_buffer[buffer_idx]
                buffer_idx += 1

        if has_target == 2:
            buffer_idx = 48020

        if has_target:
            buffer_idx += len(magic_word)

            frame_count = struct.unpack_from('I', packet_buffer, buffer_idx)[0]
            buffer_idx += 4


            target_num = struct.unpack_from('I', packet_buffer, buffer_idx)[0]
            buffer_idx += 4

            #타겟 위치 정보 및 상태 정보 부분
            for step in range(target_num):
                try:
                    pos_x, pos_y, status, target_id, reserved_1, reserved_2, reserved_3 = struct.unpack_from('ffIIfff', packet_buffer, buffer_idx)
                    if step < len(target):
                        target[step] = SRS_TARGET_INFO(pos_x, pos_y, status, target_id, [reserved_1, reserved_2, reserved_3])
                        print(pos_x, pos_y, status)
                    else:
                        print("skip target.")
                    buffer_idx += struct.calcsize('ffIIfff')
                except IndexError:
                    print("skip target")
                    continue

            for step in range(target_num):
                status_str = "UNKNOWN"
                status = target[step].status
                if status == SRS_TARGET_STATUS_WALKING:
                    status_str = "WALKING"
                elif status == SRS_TARGET_STATUS_LYING:
                    status_str = "LYING"
                elif status == SRS_TARGET_STATUS_SITTING:
                    status_str = "SITTING"
                elif status == SRS_TARGET_STATUS_FALL:
                    status_str = "FALL"
                    send_status_to_server("fall")
                sendToUnity(target[step].id,target[step].posX,target[step].posY,status_str)
                #print(f"Target[{step}] {{ID: {target[step].id}, X: {target[step].posX:3.2f}, Y: {target[step].posY:3.2f}, Status: {status_str} ({status})}}")

    sock.close()
    return 0

if __name__ == "__main__":
    main()