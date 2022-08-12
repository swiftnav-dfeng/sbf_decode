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
        self.data = block
        self.header = SBFHeader(self.data[:HEADER_SIZE])
        self.timestamp = SBFTimeStamp(self.data[HEADER_SIZE:HEADER_SIZE+TIMESTAMP_SIZE])
        self.body = self._parse_body()

    def _parse_body(self):
        cls = sbf_lookup.get(self.header.get_block_id(), SBFBody)
        return cls(self.data[HEADER_SIZE+TIMESTAMP_SIZE:], self.header.get_block_rev())

class SBFBody:
    STRUCT_FORMAT = ''
    BODY_LENGTH = 0

    def __init__(self, body: bytearray, rev=0) -> None:
        self.body = body
        self.rev = rev
        pass

class SBFPvtCartesian(SBFBody):
    STRUCT_FORMAT = '<BBdddfffffdfBBBBHHIBBH'
    BODY_LENGTH = 74
    
    STRUCT_FORMAT_V2 = '<HHHB'
    BODY_LENGTH_V2 = 7 + BODY_LENGTH

    def __init__(self, body: bytearray, rev=0) -> None:
        super().__init__(body, rev)

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
    

class SBFPvtGeodetic(SBFBody):
    STRUCT_FORMAT = '<BBdddfffffdfBBBBHHIBBH'
    BODY_LENGTH = 74
    
    STRUCT_FORMAT_V2 = '<HHHB'
    BODY_LENGTH_V2 = 7 + BODY_LENGTH

    def __init__(self, body: bytearray, rev=0) -> None:
        super().__init__(body, rev)


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

        if self.rev == 2:
            (
                self.Latency,
                self.HAccuracy,
                self.VAccuracy,
                self.Misc
            ) = struct.unpack(self.STRUCT_FORMAT_V2, self.body[self.BODY_LENGTH:self.BODY_LENGTH_V2])

            padding_start = self.BODY_LENGTH_V2

        self.padding = bytes(self.body[padding_start:])

class SBFSatVisibility(SBFBody):
    STRUCT_FORMAT = '<BB'
    BODY_LENGTH = 2

    def __init__(self, body: bytearray, rev=0) -> None:
        super().__init__(body, rev)

        self.sat_infos = []

        (
            self.N,         # number of SatInfo sub-blocks
            self.SBLength   # one sub-block length
        ) = struct.unpack(self.STRUCT_FORMAT, self.body[:self.BODY_LENGTH])

        idx = self.BODY_LENGTH
        for _ in range(self.N):
            self.sat_infos.append(SatInfo(self.body[idx:idx+self.SBLength]))
            idx += self.SBLength

        self.padding = bytes(self.body[idx:])

class SatInfo:
    STRUCT_FORMAT = '<BBHhBB'
    BODY_LENGTH = 8

    def __init__(self, sb):
        self.sb = sb

        (
            svid,
            freqnr,
            self.Azimuth,
            self.Elevation,
            self.RiseSet,
            self.SatelliteInfo
        ) = struct.unpack(self.STRUCT_FORMAT, self.sb[:self.BODY_LENGTH])

        self.SVID = SVID(svid)
        self.FreqNr = FreqNr(freqnr)

        self.padding = bytes(self.sb[self.BODY_LENGTH:])


class SBFMeasEpoch(SBFBody):
    STRUCT_FORMAT = '<BBBBBB'
    BODY_LENGTH = 6

    def __init__(self, body: bytearray, rev=0) -> None:
        super().__init__(body, rev)

        self.sub_blocks = []

        (
            self.N1,            # number of MeasEpochChannelType1 sub-blocks
            self.SB1Length,     # Length of a MeasEpochChannelType1 sub-block, excluding the nested MeasEpochChannelType2 sub-blocks
            self.SB2Length,      # Length of a MeasEpochChannelType2 sub-block
            commonflags,
            self.CumClkJumps,
            self.Reserved
        ) = struct.unpack(self.STRUCT_FORMAT, self.body[:self.BODY_LENGTH])

        self.CommonFlags = self.parse_commonflags(commonflags)

        print(self.SB1Length)

        idx = self.BODY_LENGTH
        for _ in range(self.N1): 
            sb = MeasEpochChannelType1(self.body[idx:idx+self.SB1Length])
            type2_sb = []
            t2_idx = idx + self.SB1Length
            for i in range(sb.N2):
                t2sb = MeasEpochChannelType2(self.body[t2_idx:t2_idx+self.SB2Length])
                type2_sb.append(t2sb)
                t2_idx += self.SB2Length
            self.sub_blocks.append((sb, type2_sb))
            idx = t2_idx

        self.padding = bytes(self.body[idx:])

    def parse_commonflags(self, flags:int):
        parsed = {
            'multipath_multigation' : bool(flags & 0x1),
            'code_smoothing' : bool(flags & 0x2),
            'carrier_phase_align' : bool(flags & 0x4 >> 2),
            'clock_steering' : bool(flags & 0x8),
            'high_dynamics' : bool(flags & 0x20),
            'scrambling' : bool(flags & 0x80)
        }
        return parsed

class MeasEpochChannelType1:
    STRUCT_FORMAT = '<BBBBLiHbBHBB'
    BODY_LENGTH = 20

    def __init__(self, sb):
        self.sb = sb

        (
            self.RxChannel,
            self.Type,
            svid,
            self.Misc,
            self.CodeLSB,
            self.Doppler,
            self.CarrierLSB,
            self.CarrierMSB,
            self.CN0,
            self.LockTime,
            self.ObsInfo,
            self.N2
        ) = struct.unpack(self.STRUCT_FORMAT, self.sb[:self.BODY_LENGTH])

        self.SVID = SVID(svid)
        self.SignalType = self.get_signal_type(self.Type, self.ObsInfo)

        self.padding = bytes(self.sb[self.BODY_LENGTH:])

    def get_signal_type (self, type, obsinfo):
        lsb = type & 0x1f
        if lsb != 31:
            return SignalType(lsb)
        else:
            return SignalType((obsinfo & 0xf8) >> 3)
        pass


class MeasEpochChannelType2:
    STRUCT_FORMAT = '<BBBBbBHHH'
    BODY_LENGTH = 12

    def __init__(self, sb):
        self.sb = sb

        (
            self.Type,
            self.LockTime,
            self.CN0,
            self.OffsetsMSB,
            self.CarrierMSB,
            self.ObsInfo,
            self.CodeOffsetLSB,
            self.CarrierLSB,
            self.DopplerOffsetLSB
        ) = struct.unpack(self.STRUCT_FORMAT, self.sb[:self.BODY_LENGTH])

        if self.Type == 31:
            self.SignalType = SignalType((self.ObsInfo >> 3) + 31)
        else:
            self.SignalType = SignalType(self.Type)

        self.padding = bytes(self.sb[self.BODY_LENGTH:])

sbf_lookup = {
    4012: SBFSatVisibility,
    4006: SBFPvtCartesian,
    4007: SBFPvtGeodetic,
    4027: SBFMeasEpoch
}

class SVID:
    def __init__(self, svid:int):
        self.sat_code = self.get_sat_code(svid)
    
    def get_sat_code(self, svid:int):
        if svid >= 1 and svid <= 37:
            return f'G{svid}'
        elif svid >= 38 and svid <= 61:
            return f'R{svid-37}'
        elif svid ==62:
            return f'RNA'
        elif svid >= 63 and svid <= 68:
            return f'R{svid-38}'
        elif svid >= 71 and svid <= 106:
            return f'E{svid-70}'
        elif svid >= 107 and svid <= 119:
            return f'LBandBeams-{svid}'
        elif svid >= 120 and svid <= 140:
            return f'S{svid}'
        elif svid >= 141 and svid <= 180:
            return f'C{svid-140}'
        elif svid >= 181 and svid <= 187:
            return f'J{svid-180}'
        elif svid >= 191 and svid <= 197:
            return f'I{svid-190}'
        elif svid >= 198 and svid <= 215:
            return f'S{svid-57}'
        elif svid >= 216 and svid <= 222:
            return f'I{svid-208}'
        elif svid >= 223 and svid <= 245:
            return f'C{svid-182}'
        else:
            return f'Unk-{svid}'

class FreqNr:
    def __init__(self, freqnr:int):
        # GLONASS Frequency number offset of 8
        # Do not use if not GLONASS
        self.FreqNr = self.get_freqnr(freqnr)
    
    def get_freqnr(self, freqnr:int):
        return (freqnr - 8)

class SignalType:
    SIGNAL_TYPES = {
        # Signal, Constellation, Rinex code
        0:('L1CA', 'GPS', '1C'),
        1:('L1P', 'GPS', '1W'),
        2:('L2P', 'GPS', '2W'),
        3:('L2C', 'GPS', '2L'),
        4:('L5', 'GPS', '5Q'),
        5:('L1C', 'GPS', '1L'),
        6:('L1CA', 'QZSS', '1C'),
        7:('L2C', 'QZSS', '2L'),
        8:('L1CA', 'GLONASS', '1C'),
        9:('L1P', 'GLONASS', '1P'),
        10:('L2P', 'GLONASS', '2P'),
        11:('L2CA', 'GLONASS', '2C'),
        12:('L3', 'GLONASS', '3Q'),
        13:('B1C', 'BeiDou', '1P'),
        14:('B2a', 'BeiDou', '5P'),
        15:('L5', 'NavIC/IRNSS', '5A'),
        16:('Reserved', 'Reserved', 'Reserved'),
        17:('E1 (L1BC)', 'Galileo', '1C'),
        18:('Reserved', 'Reserved', 'Reserved'),
        19:('E6 (E6BC)', 'Galileo', '6C'),
        20:('E5a', 'Galileo', '5Q'),
        21:('E5b', 'Galileo', '7Q'),
        22:('E5 AltBoc', 'Galileo', '8Q'),
        23:('LBand', 'MSS', 'NA'),
        24:('L1CA', 'SBAS', '1C'),
        25:('L5', 'SBAS', '5I'),
        26:('L5', 'QZSS', '5Q'),
        27:('L6', 'QZSS', None),
        28:('B1I', 'BeiDou', '2I'),
        29:('B2I', 'BeiDou', '7I'),
        30:('B3I', 'BeiDou', '6I'),
        31:('Reserved', 'Reserved', 'Reserved'),
        32:('L1C', 'QZSS', '1L'),
        33:('L1S', 'QZSS', '1Z'),
        34:('B2b', 'BeiDou', '7D'),
        35:('Reserved', 'Reserved', 'Reserved')       
    }

    def __init__(self, signal:int):
        self.SignalType = self.get_signal_type(signal)[0]
        self.Constellation = self.get_signal_type(signal)[1]
        self.RINEX_obs_code = self.get_signal_type(signal)[2]

    def get_signal_type(self, signal:int):
        return self.SIGNAL_TYPES[signal]
