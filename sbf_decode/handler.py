from crc import CrcCalculator, Crc16
from sbf_decode.sbf import SBFHeader
import logging

class Handler():
    def __init__(self, handle, callback):
        self.handle = handle
        self.data = bytearray()
        self.frame = bytearray()
        self.frame_length = None
        self.header = None

        self.callback = callback


    def process(self):
        while True:
            buf = bytearray(b'')
            if self.handle is not None:
                buf = bytearray(self.handle.read(1024))
            
            self.insert_data(buf)
            if len(self.data) == 0:
                break
            self.framer()
        
        logging.info('no data available, returning')

    def insert_data(self, data:bytearray):
        self.data += data

    def framer(self):
        while True:
            try:
                b = self.data.pop(0)
                if len(self.frame) == 0:
                    if chr(b) == '$':
                        self.frame = bytearray(b'$')
                elif len(self.frame) == 1:
                    if chr(b) == '@':
                        self.frame.append(b)
                    elif chr(b) == b'$':
                        self.frame = bytearray(b'$')
                    else:
                        # SBF sync sequence not found
                        self.frame = []
                elif len(self.frame) == 7:
                    # header length of 8 achieved
                    self.frame.append(b)
                    self.process_header()
                    self.frame_length = self.header.length
                    pass
                elif (self.frame_length is not None) and (len(self.frame) == self.frame_length - 1):
                    self.frame.append(b)
                    if self.check_frame():
                        self.callback(self.header, self.frame)

                        self.reset_frame()
                        pass
                    else:
                        logging.info(f"CRC check failed on data {self.frame}")
                        # crc failed, reset frame
                        # reinsert all bytes, except the first 2 sync bytes back into data
                        self.data = self.frame[2:] + self.data

                        # reset
                        self.reset_frame()

                else:
                    # in middle of SBF message, read more?
                    self.frame.append(b)
            except IndexError as e:
                # self.data is empty, get more data
                break

    def reset_frame(self):
        self.header = None
        self.frame_length = None
        self.frame = bytearray()


    def process_header(self):
        self.header = SBFHeader(self.frame)

    def check_frame(self):
        # perform crc check
        crc_calculator = CrcCalculator(Crc16.CCITT, True)

        # calculate crc without 2 sync bytes and 2 crc bytes
        checksum = crc_calculator.calculate_checksum(self.frame[4:])
        if checksum == self.header.crc:
            return True
        else:
            logging.warn(f'checksum failed header crc = {self.header.crc}, calculated = {checksum}')
            return False
        


        