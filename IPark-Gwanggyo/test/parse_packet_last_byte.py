import os
import sys
import pickle
CURPATH = os.path.dirname(os.path.abspath(__file__))
INCPATH = os.path.dirname(CURPATH)
sys.path.extend([INCPATH])
sys.path = list(set(sys.path))
from homeDef import Home
from CRC8 import CRC8

home = Home(init_service=False)
packets = []
packets.extend(home.parser_smart.elevator_down_packets)
packets.extend(home.parser_smart.elevator_up_packets)
packets = [bytearray([int(y, 16) for y in x.split(' ')]) for x in packets]

polynomials = [x for x in range(256)]
init_values = [x for x in range(256)]
ref_ins = [False, True]
ref_outs = [False, True]
xor_outpus = [x for x in range(256)]

pkl_path = os.path.abspath('./crc8list.pkl')
if os.path.isfile(pkl_path):
    with open(pkl_path, 'rb') as fp:
        crc_list = pickle.load(fp)
else:
    crc_list = []
    for poly in polynomials:
        for init_val in init_values:
            for refin in ref_ins:
                for refout in ref_outs:
                    for xorout in xor_outpus:
                        crc = CRC8(poly, init_val, refin, refout, xorout)
                        print(crc)
                        crc_list.append(crc)
    with open(pkl_path, 'wb') as fp:
        pickle.dump(crc_list, fp)
