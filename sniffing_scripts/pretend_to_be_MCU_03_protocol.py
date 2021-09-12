import serial
from time import sleep
while 1:
    try:
        # ser = serial.Serial("COM3")
        ser = serial.Serial("COM6",115200)
        break
    except PermissionError:
        pass
    except Exception as e:
        print(e)
        sleep(1)

print(ser.name)
sdu_types = {0: 'raw', 1: 'bool', 2: 'value', 3: 'string', 4: 'enum', 5: 'bitmap'}

tuya_comm = []
first_heartbeat = True
first_tell_to_reset_wifi = True
while 1:
    x = ser.read()
    if x == b'\x55':
        y = ser.read()
        if y == b'\xaa':
            ver = ser.read()
            com = ser.read()
            comm_len1 = ser.read()
            comm_len2 = ser.read()
            comm_len = int.from_bytes(comm_len1+comm_len2, 'big')
            tuya_comm = []
            tuya_comm.append(ord(x))
            tuya_comm.append(ord(y))
            tuya_comm.append(ord(ver))
            tuya_comm.append(ord(com))
            tuya_comm.append(ord(comm_len1))
            tuya_comm.append(ord(comm_len2))
            for n in range(comm_len):
                bit = ser.read()
                tuya_comm.append(ord(bit))
            chk = ser.read()
            tuya_comm.append(ord(chk))

            ts = ''.join('%02x' % b for b in tuya_comm)
            print('------\n' + ts)
            if len(tuya_comm) == 0:
                pass
            elif ts == '55aa00000000ff': 
                print('Heart Beat') # Heart Beat
                if first_heartbeat:
                    ser.write(bytearray.fromhex('55AA030000010003'))
                    first_heartbeat = False
                else:
                    ser.write(bytearray.fromhex('55AA030000010104'))
            elif tuya_comm[3] == ord(b'\x01'): 
                print('Query Product Info')
                ser.write(bytearray.fromhex('55AA0301002A7B2270223A227570696A6673346B7261727477687176222C2276223A22312E302E30222C226D223A307D9E')) # HeimVision N600S, {"p":"upijfs4krartwhqv","v":"1.0.0","m":0}
                # ser.write(bytearray.fromhex('55AA0301002A7B2270223A2263376173626867743273767568773573222C2276223A22322E302E33222C226D223A327D1F')) # Fairy Lights Controller
                # ser.write(bytearray.fromhex('55AA0301002B7B2270223A226776666D773863386E3932756D706178222C2276223A22332E332E3136222C226D223A307D2A')) # Esmlfe Fan-Light Switch, {"p":"gvfmw8c8n92umpax","v":"3.3.16","m":0}
            elif tuya_comm[3] == ord(b'\x02'): 
                print('Query Working Mode')
                ser.write(bytearray.fromhex('55AA0302000004'))
            elif tuya_comm[3] == ord(b'\x03'): 
                print('Network Status')
                ser.write(bytearray.fromhex('55AA0303000005'))

                # THIS RESETS ITS WIFI SETTINGS. We do this bc the app freaks out when the fake device isn't newly added.
                if first_tell_to_reset_wifi:
                    ser.write(bytearray.fromhex('55AA0304000006'))
                    first_tell_to_reset_wifi = False
            elif tuya_comm[3] == ord(b'\x08'): 
                print('Query Status') 
            elif tuya_comm[3] == ord(b'\x1c'): 
                print('Send Local Time')
                ser.write(bytearray.fromhex('55AA001C0008011508031731020290'))
            elif tuya_comm[3] == ord(b'\x06'):
                ts_ack = list(ts[:])
                ts_ack[5] = '3'
                ts_ack[7] = '7'
                chk1 = ts_ack[-2]
                chk2 = ts_ack[-1]
                chk = '%02X' % ((int.from_bytes(bytearray.fromhex(chk1+chk2), byteorder='big') + 4) % 256)
                ts_ack[-2] = chk[0]
                ts_ack[-1] = chk[1]
                ser.write(bytearray.fromhex(''.join(ts_ack)))

                # need to reply with ack
                print('Data Unit')
                data_len = int.from_bytes(tuya_comm[4:6], 'big')
                print('  Data Length: %d' % data_len)
                data = tuya_comm[6:7+data_len]
                print('  Data: %s' % ''.join('%02x' % b for b in data))
                n = 0
                while 1:
                    sdu_dpid = data[n]
                    sdu_type = data[n+1]
                    sdu_len = int.from_bytes(data[n+2:n+4], 'big')
                    sdu_data = data[n+4:n+4+sdu_len]

                    DpIdData = ''.join('%02x' % b for b in sdu_data)
                    print('    DPID: %d' % sdu_dpid)
                    print('    TYPE: %s' % sdu_types[sdu_type])
                    print('    DATA: %s' % DpIdData)

                    if sdu_types[sdu_type] == 'string':
                        print('    VALUE: %s' % bytearray.fromhex(DpIdData).decode())

                    if (n+4+sdu_len) == data_len:
                        break
                    else:
                        n = n+4+sdu_len
            else:
                print(ts)