"""Distance bands used by the Busan dataset; codes are ordinal, not metres."""
import re
import unicodedata
import numpy as np
import pandas as pd

LABELS = ('대기 없음', '5m 미만', '5m 이상 ~ 10m 미만', '10m 이상 ~ 15m 미만', '15m 이상')

def is_distance_target(name):
    name = str(name).replace(' ', '').replace('_', '')
    return '거리구간' in name or name == '예상대기거리구간'

def encode_distance(values):
    def encode(value):
        if pd.isna(value):
            raise ValueError('대기거리 구간에 빈 값이 있습니다. 원본을 확인해 주세요.')
        text = unicodedata.normalize('NFKC', str(value)).lower().strip()
        text = re.sub(r'\s+', '', text).replace('미터', 'm').replace('meters', 'm')
        text = text.replace('–', '~').replace('—', '~').replace('-', '~')
        aliases = {
            '대기없음': 0, '없음': 0, '0m': 0,
            '5m미만': 1, '0m~5m': 1, '0~5m': 1, '0m초과~5m미만': 1,
            '5m이상~10m미만': 2, '5m~10m': 2, '5~10m': 2,
            '10m이상~15m미만': 3, '10m~15m': 3, '10~15m': 3,
            '15m이상': 4, '15m+': 4,
        }
        if text in aliases:
            return aliases[text]
        try:
            number = float(text)
            if np.isfinite(number) and number.is_integer() and 0 <= number <= 4:
                return int(number)
        except ValueError:
            pass
        raise ValueError(f'알 수 없는 대기거리 구간: {value!r}. 대기 없음 / 5m 미만 / 5~10m / 10~15m / 15m 이상을 사용하세요.')
    return values.map(encode)

def display_distance(values):
    def display(value):
        if pd.isna(value) or not np.isfinite(value):
            return '정보 없음'
        return LABELS[int(np.clip(np.floor(float(value) + .5), 0, 4))]
    return pd.to_numeric(values, errors='coerce').map(display)


def display_wait_time(values):
    """Project-defined distance-to-wait mapping, not measured waiting time."""
    times = ('0분', '5분 미만', '5분 이상', '10분 이상', '15분 이상')
    def display(value):
        if pd.isna(value) or not np.isfinite(value):
            return '정보 없음'
        return times[int(np.clip(np.floor(float(value) + .5), 0, 4))]
    return pd.to_numeric(values, errors='coerce').map(display)
