import struct
import logging
from pandas import DataFrame

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

    def get_obs_dataframe(self):
        obs = {
            'SVID': [],
            'SignalType': [],
            'Constellation': [],
            'CN0': [],
            'Pseudorange (m)': [],
            'Doppler (Hz)': [],
            'Carrier Phase (Cycles)': [],
            'Locktime (s)': []
        }

        for sb1, sb2_list in self.sub_blocks:
            obs['SVID'].extend([sb1.SVID.sat_code] * (len(sb2_list) + 1))
            obs['Constellation'].extend([sb1.SignalType.Constellation] * (len(sb2_list) + 1))

            freq1 = sb1.SignalType.Frequency

            obs['SignalType'].append(sb1.SignalType.SignalType)
            obs['CN0'].append(sb1.get_CN0())

            pseudorange = None
            if (sb1.Misc & 0xf) != 0 or sb1.CodeLSB != 0:
                pseudorange = ((sb1.Misc & 0xf) * 4294967296 + sb1.CodeLSB) * 0.001
            obs['Pseudorange (m)'].append(pseudorange)

            doppler = None
            if (sb1.Doppler != -2147483648):
                doppler = sb1.Doppler * 0.0001
            obs['Doppler (Hz)'].append(doppler)

            carrier_phase = None
            if sb1.CarrierMSB != -128 or sb1.CarrierLSB != 0:
                carrier_phase = pseudorange / (299792458/sb1.SignalType.Frequency) + (sb1.CarrierMSB * 65536 + sb1.CarrierLSB) * 0.001
            obs['Carrier Phase (Cycles)'].append(carrier_phase)

            obs['Locktime (s)'].append(sb1.LockTime)

            for sb2 in sb2_list:
                #re calculate signal type in case of GLONASS
                freq2 = sb2.SignalType.Frequency
                if (sb2.SignalType.id >= 8) and (sb2.SignalType.id <= 11):
                    #GLO
                    freq2 = SignalType(sb2.Type, sb1.ObsInfo).Frequency

                obs['SignalType'].append(sb2.SignalType.SignalType)
                obs['CN0'].append(sb2.get_CN0())
                
                pr2 = None
                if pseudorange is not None and (sb2.CodeOffsetMSB != -4 or sb2.CodeOffsetLSB != 0):
                    pr2 = pseudorange + (sb2.CodeOffsetMSB * 65536 + sb2.CodeOffsetLSB) * 0.001
                obs['Pseudorange (m)'].append(pr2)

                d2 = None
                if doppler is not None and (sb2.DopplerOffsetMSB != -16 or sb2.DopplerOffsetLSB != 0):
                    d2 = doppler * freq2/freq1 + (sb2.DopplerOffsetMSB * 65536 + sb2.DopplerOffsetLSB) * 1e-4
                obs['Doppler (Hz)'].append(d2)

                cp2 = None
                if sb2.CarrierMSB != -128 and sb1.CarrierLSB != 0:
                    cp2 = pr2 / (299792458/freq2) + (sb2.CarrierMSB * 65536 + sb2.CarrierLSB) * 0.001
                obs['Carrier Phase (Cycles)'].append(cp2)

                obs['Locktime (s)'].append(sb2.LockTime)

        return DataFrame.from_dict(obs)

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

        self.SigIdxLo = self.Type & 0x1f
        self.AntennaID = (self.Type & 0xe0) >> 5
        self.SignalType = SignalType(self.SigIdxLo, self.ObsInfo)

        self.padding = bytes(self.sb[self.BODY_LENGTH:])
    
    def get_CN0(self):
        if self.SignalType.SignalType == 1 or self.SignalType.SignalType == 2:
            return self.CN0 * 0.25
        else:
            return self.CN0 * 0.25 + 10
        


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

        self.SigIdxLo = self.Type & 0x1f
        self.AntennaID = (self.Type & 0xe0) >> 5
        self.SignalType = SignalType(self.SigIdxLo, self.ObsInfo)

        self.CodeOffsetMSB = twos_comp(self.OffsetsMSB & 0x7, 3)
        self.DopplerOffsetMSB = twos_comp((self.OffsetsMSB & 0xf8) >> 3, 5)

        self.padding = bytes(self.sb[self.BODY_LENGTH:])

    def get_CN0(self):
        if self.SignalType.SignalType == 1 or self.SignalType.SignalType == 2:
            return self.CN0 * 0.25
        else:
            return self.CN0 * 0.25 + 10

def twos_comp(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val                         # return positive value as is
        

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
        # Signal, Constellation, Rinex code, Frequency (MHz)
        0:('L1CA', 'GPS', '1C', 1575.42),
        1:('L1P', 'GPS', '1W', 1575.42),
        2:('L2P', 'GPS', '2W', 1227.60),
        3:('L2C', 'GPS', '2L', 1227.60),
        4:('L5', 'GPS', '5Q', 1176.45),
        5:('L1C', 'GPS', '1L', 1575.42),
        6:('L1CA', 'QZSS', '1C', 1575.42),
        7:('L2C', 'QZSS', '2L', 1227.60),
        8:('L1CA', 'GLONASS', '1C', 1602.0),
        9:('L1P', 'GLONASS', '1P', 1602.0),
        10:('L2P', 'GLONASS', '2P', 1246.0),
        11:('L2CA', 'GLONASS', '2C', 1246.0),
        12:('L3', 'GLONASS', '3Q', 1202.025),
        13:('B1C', 'BeiDou', '1P', 1575.42),
        14:('B2a', 'BeiDou', '5P', 1176.45),
        15:('L5', 'NavIC/IRNSS', '5A', 1176.45),
        16:('Reserved', 'Reserved', 'Reserved', None),
        17:('E1 (L1BC)', 'Galileo', '1C', 1575.42),
        18:('Reserved', 'Reserved', 'Reserved', None),
        19:('E6 (E6BC)', 'Galileo', '6C', 1278.75),
        20:('E5a', 'Galileo', '5Q', 1176.45),
        21:('E5b', 'Galileo', '7Q', 1207.14),
        22:('E5 AltBoc', 'Galileo', '8Q', 1191.795),
        23:('LBand', 'MSS', 'NA', None),
        24:('L1CA', 'SBAS', '1C', 1575.42),
        25:('L5', 'SBAS', '5I', 1176.45),
        26:('L5', 'QZSS', '5Q', 1176.45),
        27:('L6', 'QZSS', None, 1278.75),
        28:('B1I', 'BeiDou', '2I', 1561.098),
        29:('B2I', 'BeiDou', '7I', 1207.14),
        30:('B3I', 'BeiDou', '6I', 1268.52),
        31:('Reserved', 'Reserved', 'Reserved', None),
        32:('L1C', 'QZSS', '1L', 1575.42),
        33:('L1S', 'QZSS', '1Z', 1575.42),
        34:('B2b', 'BeiDou', '7D', 1207.14),
        35:('Reserved', 'Reserved', 'Reserved', None)       
    }

    def __init__(self, type:int, obsinfo:int):
        self.id = self.get_signal_type(type, obsinfo)
        self.SignalType = self.SIGNAL_TYPES[self.id][0]
        self.Constellation = self.SIGNAL_TYPES[self.id][1]
        self.RINEX_obs_code = self.SIGNAL_TYPES[self.id][2]
        self.Frequency = self.get_frequency(obsinfo)

    def get_signal_type (self, type, obsinfo):
        lsb = type & 0x1f
        if lsb != 31:
            return lsb
        else:
            return ((obsinfo & 0xf8) >> 3) + 32

    def get_frequency(self, obsinfo:int):
        f = None
        if self.id == 8 or self.id == 9:
            f = self.SIGNAL_TYPES[self.id][3] + ((((obsinfo & 0xf8) >> 3) - 8) * 9/16)
        elif self.id == 10 or self.id == 11:
            f = self.SIGNAL_TYPES[self.id][3] + ((((obsinfo & 0xf8) >> 3) - 8) * 7/16)
        else:
            f = self.SIGNAL_TYPES[self.id][3]

        return f * 1e6  # return Hz
