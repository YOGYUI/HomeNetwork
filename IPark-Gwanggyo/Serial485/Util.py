from typing import List, Dict, Union
from PyQt5 import QtSerialPort


def list_serial() -> List[Dict[str, Union[str, int, bool]]]:
    available = QtSerialPort.QSerialPortInfo().availablePorts()
    lst = [{
        'port': x.portName(),
        'manufacturer': x.manufacturer(),
        'description': x.description(),
        'serialnumber': x.serialNumber(),
        'systemlocation': x.systemLocation(),
        'productidentifier': x.productIdentifier(),
        'vendoridentifier': x.vendorIdentifier(),
        'isbusy': x.isBusy(),
        'isvalid': x.isValid()
        } for x in available]
    return lst


if __name__ == '__main__':
    serial_list = list_serial()
    for elem in serial_list:
        print('{')
        for i, (key, value) in enumerate(elem.items()):
            print("    '{}': '{}'".format(key, value), end='')
            if i == len(elem.items()) - 1:
                print('')
            else:
                print(',')
        print('}')
