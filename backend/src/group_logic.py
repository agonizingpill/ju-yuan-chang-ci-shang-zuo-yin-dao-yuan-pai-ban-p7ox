from datetime import datetime,timedelta,timezone,date
# 剧场本地时间固定为 Asia/Shanghai（UTC+8，无夏令时），与项目其他模块口径一致。
LOCAL=timezone(timedelta(hours=8))
def cutoff_before(day):
    """开场前一天已知的截止时刻：开场日 00:00（剧场本地）。早于该时刻的变动才算已知。"""
    return datetime(day.year,day.month,day.day,tzinfo=LOCAL)
def parse_stamp(text):
    dt=datetime.fromisoformat(text)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=LOCAL)
def replay_booked(changes,cutoff):
    """按记录时刻回放一条预订的变动台账，返回截止时刻已知的预订人数。

    截止时还没有任何变动记录返回 None（未知，不等于 0）。
    changes 元素需有 id、booked_count、recorded_at 属性（或同名字典键）。
    """
    def val(c,k):return c[k] if isinstance(c,dict) else getattr(c,k)
    known=[c for c in changes if parse_stamp(val(c,'recorded_at'))<cutoff]
    if not known:return None
    latest=max(known,key=lambda c:(parse_stamp(val(c,'recorded_at')),val(c,'id')))
    return val(latest,'booked_count')
def known_at(bookings_with_changes,cutoff):
    """某场在截止时刻已知的团体预订合计。

    没有任何预订记录返回 None（旧场只有总验票，不能当成没有团体）；
    有预订但全部晚于截止才录入，返回 0（当时确实已知为零，晚到记录不计入）。
    """
    if not bookings_with_changes:return None
    return sum(replay_booked(changes,cutoff) or 0 for _,changes in bookings_with_changes)
def actual_total(bookings):
    """某场团体实到合计。无预订或任一预订未登记实到都返回 None（未对账，拆分未知）。"""
    if not bookings:return None
    if any(b.actual_count is None for b in bookings):return None
    return sum(b.actual_count for b in bookings)
def walkin_series(rows,actual_by_perf):
    """末尾连续已核账场次的散客序列（总验票 − 团体实到）。

    只有总验票、缺少团体对账的旧场会截断序列，而不是按 0 团体处理。
    """
    series=[]
    for r in reversed(rows):
        actual=actual_by_perf.get(r.id)
        if actual is None:break
        series.append(r.arrivals-actual)
    series.reverse()
    return series
def future_group_est(bookings_with_changes,now):
    """未来场的团体估计：预测运行时刻已知的预订合计（无预订即 0）。"""
    return sum(replay_booked(changes,now) or 0 for _,changes in bookings_with_changes)
