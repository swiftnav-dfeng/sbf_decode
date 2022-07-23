from sbf_decode.drivers.driver import BaseDriver
from gnss_receivers.septentrio.receiver_septentrio import SeptentrioReceiver
from base64 import b64decode


class HttpDriver(BaseDriver):
    def __init__(self, address: str, port: int, username: str = None, password: str = None):
        self.address = address
        self.port = port
        self.username = username
        self.password = password

        self.rx = None
        self.sbf_reader = None

        self.buf = bytearray()


    def __enter__(self):
        self.rx = SeptentrioReceiver(self.address, self.port, (self.username, self.password))
        self.rx.http_login()
        #self.sbf_reader = SBFReader(self.read)
        #return self.sbf_reader
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.rx is not None:
            self.rx.http_logout()
        
    def open(self):
        return self.__enter__()

    def read(self, bytes = 1):
        blk = b''

        if len(self.buf) == 0:
            blk_b64 = self.rx.get_sbf_block()
            blk_b64 = blk_b64.split('\r\n')
            blk_b64_str = ''
            for line in blk_b64:
                blk_b64_str += line
            blk = b64decode(blk_b64_str.encode('ASCII'))
            self.buf += blk

        
        ret, self.buf = self.buf[:bytes], self.buf[bytes:]

        return ret