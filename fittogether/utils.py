from datetime import datetime, timedelta
from django.utils import timezone

# centralización de la función week_bounds, esto para poder sacarla de otros archivos y no tenerla repetida
def week_bounds(local_day):

    start_day = local_day - timedelta(days=local_day.weekday())  # Monday
    start_dt = timezone.make_aware(datetime.combine(start_day, datetime.min.time()))
    end_dt = start_dt + timedelta(days=7)
    return start_dt, end_dt
