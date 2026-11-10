#!/usr/bin/env python3
"""只读核验本次保存的二进制PCD：尺寸、点数、数据长度和抽样XYZ。

不加载整张地图进内存，不把原始点云写进JSON，也不修改PCD。
"""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pcd', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
result = {'checked_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
          'path': str(args.pcd), 'passed': False,
          'scope': '文件结构与抽样坐标有限性，不验证建图精度。'}
try:
    # 头部限定64行和每行4096字节，避免把异常文件当无界文本读取。
    header = {}
    with args.pcd.open('rb') as stream:
        for _ in range(64):
            raw = stream.readline(4097)
            if len(raw) > 4096 or not raw:
                raise ValueError('PCD头部异常或缺少DATA')
            line = raw.decode('ascii').strip()
            if not line or line.startswith('#'):
                continue
            key, _, value = line.partition(' ')
            header[key] = value
            if key == 'DATA':
                break
        if header.get('DATA') != 'binary':
            raise ValueError('当前检查器要求PCL写出的binary PCD')
        data_offset = stream.tell()
        fields = header['FIELDS'].split()
        sizes = [int(value) for value in header['SIZE'].split()]
        types = header['TYPE'].split()
        counts = [int(value) for value in header['COUNT'].split()]
        if not len(fields) == len(sizes) == len(types) == len(counts):
            raise ValueError('字段描述长度不一致')
        if any(size <= 0 for size in sizes) or any(count <= 0 for count in counts):
            raise ValueError('字段尺寸或COUNT非法')
        points = int(header['POINTS'])
        width, height = int(header['WIDTH']), int(header['HEIGHT'])
        if points <= 0 or points != width * height:
            raise ValueError('点数为空或与宽高不一致')
        step = sum(size * count for size, count in zip(sizes, counts))
        payload_bytes = args.pcd.stat().st_size - data_offset
        if payload_bytes != points * step:
            raise ValueError('二进制数据长度与点数及字段尺寸不一致')
        # 用头部字段偏移解析XYZ，不假定intensity的位置或固定点尺寸。
        offsets = {}
        cursor = 0
        for field, size, kind, count in zip(fields, sizes, types, counts):
            if field in ('x', 'y', 'z'):
                if kind != 'F' or size not in (4, 8) or count != 1:
                    raise ValueError('XYZ字段格式不支持')
                offsets[field] = (cursor, '<f' if size == 4 else '<d')
            cursor += size * count
        if set(offsets) != {'x', 'y', 'z'}:
            raise ValueError('缺少XYZ字段')
        # 均匀抽样最多1024点；记录范围，拒绝NaN或无穷值。
        samples = min(points, 1024)
        minimum, maximum = [math.inf] * 3, [-math.inf] * 3
        for index in range(samples):
            point_index = index * (points - 1) // max(1, samples - 1)
            stream.seek(data_offset + point_index * step)
            raw = stream.read(step)
            xyz = [struct.unpack_from(offsets[axis][1], raw, offsets[axis][0])[0]
                   for axis in ('x', 'y', 'z')]
            if not all(math.isfinite(value) for value in xyz):
                raise ValueError('抽样点XYZ含NaN或无穷值')
            minimum = [min(old, value) for old, value in zip(minimum, xyz)]
            maximum = [max(old, value) for old, value in zip(maximum, xyz)]
    digest = hashlib.sha256()
    with args.pcd.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    result.update(passed=True, points=points, bytes=args.pcd.stat().st_size,
                  payload_bytes=payload_bytes, expected_payload_bytes=points * step,
                  sampled_points=samples, sampled_xyz_min=minimum, sampled_xyz_max=maximum,
                  sha256=digest.hexdigest(), header=header)
except Exception as error:
    result['error'] = f'{type(error).__name__}: {error}'
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['passed'] else 1)
