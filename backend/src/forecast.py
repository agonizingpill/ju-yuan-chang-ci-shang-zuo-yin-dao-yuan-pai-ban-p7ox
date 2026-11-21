from datetime import timedelta,datetime,timezone
from math import ceil
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sqlalchemy import select
from .services import history,validate_history
from .models import Performance
from .group_models import GroupBooking,GroupBookingChange
from . import group_logic as gl

def fit(values):return ExponentialSmoothing(np.array(values,dtype=float),trend='add',seasonal='add',seasonal_periods=7,initialization_method='estimated').fit(optimized=True)
def ledger(s,production_id):
    """该剧目全部场次的团体预订与变动台账，按场次分组。"""
    perf_ids=s.scalars(select(Performance.id).where(Performance.production_id==production_id)).all()
    if not perf_ids:return {}
    bookings=s.scalars(select(GroupBooking).where(GroupBooking.performance_id.in_(perf_ids))).all()
    if not bookings:return {}
    changes=s.scalars(select(GroupBookingChange).where(GroupBookingChange.booking_id.in_([b.id for b in bookings])).order_by(GroupBookingChange.id)).all()
    by_booking={}
    for c in changes:by_booking.setdefault(c.booking_id,[]).append(c)
    by_perf={}
    for b in bookings:by_perf.setdefault(b.performance_id,[]).append((b,by_booking.get(b.id,[])))
    return by_perf
def forecast_week(s,production):
    rows=history(s,production.id);validate_history(rows)
    y=[r.arrivals for r in rows];train=y[:-7];test=y[-7:]
    back=fit(train).forecast(7);mae=float(np.mean(np.abs(np.array(test)-back)))
    pred=fit(y).forecast(7)
    by_perf=ledger(s,production.id)
    bookings_of=lambda p:[b for b,_ in by_perf.get(p.id,[])]
    actual_by_perf={p.id:a for p in rows if (a:=gl.actual_total(bookings_of(p))) is not None}
    walkin=gl.walkin_series(rows,actual_by_perf)
    holdout=rows[-7:]
    # 回测逐日重建“开场前一天已知”的预订；晚到的变动记录不计入，无团体记录的旧场保持未知。
    known_t1={r.date:gl.known_at(by_perf.get(r.id,[]),gl.cutoff_before(r.date)) for r in holdout}
    # 散客序列与总模型同口径：至少 28 天训练 + 7 天回测，即末尾连续 35 天已核账。
    if len(walkin)>=35:
        walkin_back=list(fit(walkin[:-7]).forecast(7));walkin_pred=list(fit(walkin).forecast(7))
        walkin_method='holt_winters'
        walkin_note=f'散客序列取末尾连续 {len(walkin)} 天已核账场次（总验票 − 团体实到），拟合 Holt-Winters 周季节模型；不足 35 天的剧目改用总模型扣减法。'
    else:
        walkin_back=walkin_pred=None
        walkin_method='total_minus_group'
        walkin_note=f'已核账散客样本仅 {len(walkin)} 天，不足 35 天无法独立拟合：散客估值 = 总验票模型预测 − 团体估计（不低于 0）。只有总验票的旧场不按 0 团体计入样本。'
    backtest=[];combined_err=[]
    for i,r in enumerate(holdout):
        g_known=known_t1[r.date];g_actual=actual_by_perf.get(r.id)
        if walkin_back is not None:w_est=max(0.0,float(walkin_back[i]))
        else:w_est=None if g_known is None else max(0.0,float(back[i])-g_known)
        combined=None if g_known is None else round(w_est+g_known,2)
        if combined is not None:combined_err.append(abs(r.arrivals-combined))
        backtest.append({'date':r.date.isoformat(),'actual':r.arrivals,'predicted':round(float(back[i]),2),'group_known':g_known,'group_actual':g_actual,'walkin_actual':None if g_actual is None else r.arrivals-g_actual,'combined':combined})
    now=datetime.now(timezone.utc);output=[]
    for i,value in enumerate(pred):
        day=rows[-1].date+timedelta(days=i+1)
        perf=s.scalar(select(Performance).where(Performance.production_id==production.id,Performance.date==day))
        if not perf:perf=Performance(production_id=production.id,date=day,curtain='19:30',status='scheduled');s.add(perf);s.flush()
        if perf.arrivals is not None or perf.status=='crew_confirmed':raise ValueError('未来场次已有验票或确认点名，不得覆盖')
        g_est=gl.future_group_est(by_perf.get(perf.id,[]),now)
        w_est=max(0.0,float(walkin_pred[i])) if walkin_pred is not None else max(0.0,float(value)-g_est)
        raw=g_est+w_est;perf.raw_forecast=round(raw,2);perf.forecast=min(production.seats,ceil(raw));perf.status='forecasted'
        output.append({'date':day.isoformat(),'group':g_est,'walkin':round(w_est,2),'raw':round(raw,2),'capped':perf.forecast,'required_ushers':max(1,ceil(perf.forecast/40))})
    return {'backtest_mae':round(mae,3),'combined_mae':None if not combined_err else round(float(np.mean(combined_err)),3),'combined_days':len(combined_err),'train_days':len(train),'holdout_days':7,'history_days':len(y),'holdout_start':rows[-7].date.isoformat(),'history_end':rows[-1].date.isoformat(),'backtest':backtest,'future':output,'method':'Holt-Winters additive trend + additive weekly seasonality (7)','group_method':'团体估计 = 开场前一天 00:00（剧场本地）前已登记的预订合计，按变动台账的记录时刻回放；未来场取预测运行时已知合计。','walkin_method':walkin_method,'walkin_method_note':walkin_note,'walkin_train_days':len(walkin),'seat_capacity':production.seats}
