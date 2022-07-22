import struct
import logging

HEADER_SIZE = 8
TIMESTAMP_SIZE = 6

class SBFHeader:
    def __init__(self, header:bytearray):
        # 8 byte header
        (self.sync1, self.sync2, self.crc, self.ID, self.length) = struct.unpack('<ccHHH',bytes(header))
        pass

    def get_block_id(self):
        #bits 0-12 of ID
        return self.ID & 0x1fff

    def get_block_rev(self):
        #bits 13-15 of ID
        return (self.ID & 0xe000) >> 13

class SBFTimeStamp:
    def __init__(self, timestamp:bytearray):
        # 6 bytes
        # TOW 1 millesecond
        # WNc 1 week
        (self.TOW, self.WNc) = struct.unpack('<IH', timestamp)

class SBFBlock:

    def __init__(self, block: bytearray):
        self.header = SBFHeader(block[:HEADER_SIZE])
        self.timestamp = SBFTimeStamp(block[HEADER_SIZE:HEADER_SIZE+TIMESTAMP_SIZE])
        self.body = block[HEADER_SIZE+TIMESTAMP_SIZE:]

class SBFPvtCartesian(SBFBlock):
    STRUCT_FORMAT = '<BBdddfffffdfBBBBHHIBBH'
    BODY_LENGTH = 74
    
    STRUCT_FORMAT_V2 = '<HHHB'
    BODY_LENGTH_V2 = 7 + BODY_LENGTH

    def __init__(self, block: bytearray):
        super().__init__(block)

        rev = self.header.get_block_rev()

        # parse v1
        (
            self.Mode, 
            self.Error, 
            self.X, 
            self.Y, 
            self.Z, 
            self.Undulation,
            self.Vx,
            self.Vy,
            self.Vz,
            self.COG,
            self.RxClkBias,
            self.RxClkDrift,
            self.TimeSystem,
            self.Datum,
            self.NrSV,
            self.WACorrInfo,
            self.ReferenceID,
            self.MeanCorrAge,
            self.SignalInfo,
            self.AlertFlag,
            self.NrBases,
            self.PPPInfo
        ) = struct.unpack(self.STRUCT_FORMAT, self.body[:self.BODY_LENGTH])

        padding_start = self.BODY_LENGTH

        if rev == 2:
            (
                self.Latency,
                self.HAccuracy,
                self.VAccuracy,
                self.Misc
            ) = struct.unpack(self.STRUCT_FORMAT_V2, self.body[self.BODY_LENGTH:self.BODY_LENGTH_V2])

            padding_start = self.BODY_LENGTH_V2

        self.padding = bytes(self.body[padding_start:])

class SBFPvtGeodetic(SBFBlock):
    STRUCT_FORMAT = '<BBdddfffffdfBBBBHHIBBH'
    BODY_LENGTH = 74
    
    STRUCT_FORMAT_V2 = '<HHHB'
    BODY_LENGTH_V2 = 7 + BODY_LENGTH

    def __init__(self, block: bytearray):
        super().__init__(block)

        rev = self.header.get_block_rev()

        # parse v1
        (
            self.Mode, 
            self.Error, 
            self.Latitude, 
            self.Longitude, 
            self.Height, 
            self.Undulation,
            self.Vn,
            self.Ve,
            self.Vu,
            self.COG,
            self.RxClkBias,
            self.RxClkDrift,
            self.TimeSystem,
            self.Datum,
            self.NrSV,
            self.WACorrInfo,
            self.ReferenceID,
            self.MeanCorrAge,
            self.SignalInfo,
            self.AlertFlag,
            self.NrBases,
            self.PPPInfo
        ) = struct.unpack(self.STRUCT_FORMAT, self.body[:self.BODY_LENGTH])

        padding_start = self.BODY_LENGTH

        if rev == 2:
            (
                self.Latency,
                self.HAccuracy,
                self.VAccuracy,
                self.Misc
            ) = struct.unpack(self.STRUCT_FORMAT_V2, self.body[self.BODY_LENGTH:self.BODY_LENGTH_V2])

            padding_start = self.BODY_LENGTH_V2

        self.padding = bytes(self.body[padding_start:])

class SBFSatVisibility(SBFBlock):
    STRUCT_FORMAT = '<BB'
    BODY_LENGTH = 2

    def __init__(self, block: bytearray):
        super().__init__(block)

        self.sat_infos = []

        (
            self.N,         # number of SatInfo sub-blocks
            self.SBLength   # one sub-block length
        ) = struct.unpack(self.STRUCT_FORMAT, self.body[:self.BODY_LENGTH])

        padding_start = self.BODY_LENGTH

        for i in range(self.N):
            idx = self.BODY_LENGTH+i*self.SBLength
            self.sat_infos.append(SatInfo(self.body[idx:idx+self.SBLength]))
            padding_start += self.SBLength

        self.padding = bytes(self.body[padding_start:])

class SatInfo:
    STRUCT_FORMAT = '<BBHhBB'
    BODY_LENGTH = 8

    def __init__(self, sb):
        self.sb = sb

        (
            self.SVID,
            self.FreqNr,
            self.Azimuth,
            self.Elevation,
            self.RiseSet,
            self.SatelliteInfo
        ) = struct.unpack(self.STRUCT_FORMAT, self.sb[:self.BODY_LENGTH])

        self.SVID = SVID(self.SVID)
        self.FreqNr = FreqNr(self.FreqNr)

        self.padding = bytes(self.sb[self.BODY_LENGTH:])




sbf_lookup = {
    4012: SBFSatVisibility,
    4006: SBFPvtCartesian,
    4007: SBFPvtGeodetic
}

class SVID:
    def __init__(self, SVID):
        self.SVID = SVID
        self.sat_code = self.get_sat_code()
    
    def get_sat_code(self):
        if self.SVID >= 1 and self.SVID <= 37:
            return f'G{self.SVID}'
        elif self.SVID >= 38 and self.SVID <= 61:
            return f'R{self.SVID-37}'
        elif self.SVID ==62:
            return f'RNA'
        elif self.SVID >= 63 and self.SVID <= 68:
            return f'R{self.SVID-38}'
        elif self.SVID >= 71 and self.SVID <= 106:
            return f'E{self.SVID-70}'
        elif self.SVID >= 107 and self.SVID <= 119:
            return f'LBandBeams-{self.SVID}'
        elif self.SVID >= 120 and self.SVID <= 140:
            return f'S{self.SVID}'
        elif self.SVID >= 141 and self.SVID <= 180:
            return f'C{self.SVID-140}'
        elif self.SVID >= 181 and self.SVID <= 187:
            return f'J{self.SVID-180}'
        elif self.SVID >= 191 and self.SVID <= 197:
            return f'I{self.SVID-190}'
        elif self.SVID >= 198 and self.SVID <= 215:
            return f'S{self.SVID-57}'
        elif self.SVID >= 216 and self.SVID <= 222:
            return f'I{self.SVID-208}'
        elif self.SVID >= 223 and self.SVID <= 245:
            return f'C{self.SVID-182}'
        else:
            return f'Unk-{self.SVID}'

class FreqNr:
    def __init__(self, FreqNr):
        # GLONASS Frequency number offset of 8
        # Do not use if not GLONASS
        self.FreqNr = FreqNr - 8