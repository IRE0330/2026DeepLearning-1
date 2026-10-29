"""Cooperative cancellation, checked between source frames and preparation steps."""
class AnalysisStopped(Exception):
    pass


def check_stop(event):
    if event is not None and event.is_set():
        raise AnalysisStopped('Stop requested; completed prefix preserved.')
