"""Cached country calendars. No paid API or network request during forecasting."""
from functools import lru_cache
from datetime import timedelta
import pandas as pd


@lru_cache(maxsize=256)
def holiday_calendar(country,year):
    import holidays
    return holidays.country_holidays(country,years=[year-1,year,year+1],observed=True,
                                    expand=False,language='ko' if country=='KR' else 'en_US')


@lru_cache(maxsize=100000)
def features_for_day(day,country='KR'):
    weekend=day.weekday()>=5
    if country:
        calendar=holiday_calendar(country,day.year)
        holiday=day in calendar
        previous=day-timedelta(days=1) in calendar
        following=day+timedelta(days=1) in calendar
        name=str(calendar.get(day,''))
    else:
        holiday=previous=following=False;name=''
    def off(d):
        return d.weekday()>=5 or (bool(country) and d in calendar)
    before=after=0
    if off(day):
        while before<14 and off(day-timedelta(days=before+1)):before+=1
        while after<14 and off(day+timedelta(days=after+1)):after+=1
    return {'days_to_holiday':next((i for i in range(15) if country and day+timedelta(days=i) in calendar),15),
            'days_since_holiday':next((i for i in range(15) if country and day-timedelta(days=i) in calendar),15),
            'day_off_run_length':before+after+1 if off(day) else 0,
            'day_off_run_position':before+1 if off(day) else 0,
            'is_holiday':int(holiday),'holiday_name':name or '공휴일 아님',
            'is_day_before_holiday':int(following),'is_day_after_holiday':int(previous),
            'is_day_off':int(weekend or holiday),
            'is_bridge_day':int(not weekend and not holiday and
                               (previous or (day-timedelta(days=1)).weekday()>=5) and
                               (following or (day+timedelta(days=1)).weekday()>=5))}


def calendar_features(timestamp,country='KR'):
    ts=pd.Timestamp(timestamp)
    result=dict(features_for_day(ts.date(),country))
    result['holiday_hour']=result['holiday_name']+'|'+str(ts.hour)
    return result
