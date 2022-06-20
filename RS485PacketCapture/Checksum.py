from functools import reduce

packet_string_list = [
    'F7 0B 01 19 01 40 10 00 00 B5 EE',
    'F7 0B 01 19 02 40 11 01 00 B6 EE',
    'F7 0B 01 19 02 40 12 01 00 B5 EE',
    'F7 0B 01 19 01 40 20 00 00 85 EE',
    'F7 0B 01 19 01 40 30 00 00 95 EE',
    'F7 0B 01 19 01 40 40 00 00 E5 EE',
    'F7 0B 01 19 01 40 60 00 00 C5 EE',
    'F7 0C 01 19 04 40 60 00 02 02 C7 EE',
    'F7 0D 01 19 04 40 10 00 01 01 01 B7 EE',
    'F7 0B 01 19 04 40 40 00 02 E2 EE',
    'F7 0B 01 1F 01 40 60 00 00 C3 EE',
    'F7 1C 01 1F 04 40 60 00 61 01 00 00 00 00 00 00 02 62 01 00 00 00 00 00 00 02 D2 EE'
]

def convert(byte_str: str):
    return bytearray([int(x, 16) for x in byte_str.split(' ')])

packets = [convert(x)for x in packet_string_list]

def calc(packet: bytearray):
    checksum_in_packet = packet[-2]
    """
    checksum_calc = 0
    for i in range(0, len(packet) - 2):
        checksum_calc = checksum_calc ^ packet[i]
    """
    checksum_calc = reduce(lambda x, y: x ^ y, packet[:-2], 0)
    print('checksum_in_packet: %02X, checksum_calc: %02X' % (checksum_in_packet, checksum_calc))

for p in packets:
    calc(p)
