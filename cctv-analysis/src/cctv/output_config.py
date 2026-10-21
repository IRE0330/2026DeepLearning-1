"""Output cadence is independent of frame analysis and record sampling."""
import math


def output_settings(config=None):
    from .config import load
    config = config or {}
    defaults = load('configs/streaming.json')
    result = {k: config.get(k, defaults[k]) for k in ('csv_split_interval_s', 'prediction_mode')}
    result['delivery'] = {**defaults['delivery'], **config.get('delivery', {})}
    if type(result['csv_split_interval_s']) is not int or result['csv_split_interval_s'] not in (3600, 86400):
        raise ValueError('csv_split_interval_s must be 3600 (hourly) or 86400 (legacy daily).')
    if result['prediction_mode'] not in ('disabled', 'mock'):
        raise ValueError('prediction_mode must be disabled or mock; no real model is configured.')
    delivery = result['delivery']
    for key in ('queue_capacity', 'max_attempts'):
        if type(delivery[key]) is not int or delivery[key] < 1:
            raise ValueError(f'delivery.{key} must be a positive integer.')
    for key in ('retry_delay_s', 'shutdown_timeout_s', 'mock_delay_s'):
        value = delivery[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f'delivery.{key} must be finite and nonnegative.')
    return result
