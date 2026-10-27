"""Instrumentation for the unchanged confirmed-only waiting policy."""
def confirmed_external(state,row):
    external=state['waiting_confirmed_observed']+state['waiting_grace']
    # Candidates are intentionally excluded. Every consistency check remains.
    if state['waiting_observed']!=state['waiting_confirmed_observed']:
        raise AssertionError('Confirmed observed waiting state mismatch')
    if external!=state['waiting_total'] or external!=int(row['외부대기인원_추정']):
        raise AssertionError('Confirmed external waiting CSV/state mismatch')
    return external
