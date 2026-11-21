from datetime import datetime,timezone
from sqlalchemy import select,func
from fastapi import HTTPException
from .models import Production,Performance
from .group_models import GroupBooking,GroupBookingChange
from .services import get,pack,audit,invalidate
from .staff_service import locked

def now():return datetime.now(timezone.utc).isoformat()
def changes_of(s,booking_id):return s.scalars(select(GroupBookingChange).where(GroupBookingChange.booking_id==booking_id).order_by(GroupBookingChange.id)).all()
def current_count(s,booking_id):
    changes=changes_of(s,booking_id)
    return changes[-1].booked_count if changes else None
def booking_view(s,b):
    changes=changes_of(s,b.id)
    return pack(b)|{'booked_count':changes[-1].booked_count if changes else None,'changes':[pack(c) for c in changes]}
def actual_sum(s,performance_id):
    return s.scalar(select(func.coalesce(func.sum(GroupBooking.actual_count),0)).where(GroupBooking.performance_id==performance_id))
def ensure_reconciled(s,performance_id,arrivals):
    """对账口径：同场团体实到合计不得超过总验票。校正总验票或登记实到时都要过这道检查。"""
    total=actual_sum(s,performance_id)
    if arrivals is not None and total>arrivals:raise HTTPException(409,f'团体实到合计 {total} 人超过总验票 {arrivals} 人，请先更正团体实到')
def mutable_performance(s,performance_id):
    """锁定场次并走失效链：补录与预测重算并发时，受影响的旧预测不能继续用于确认点名。"""
    perf=locked(s,Performance,performance_id)
    prod=get(s,Production,perf.production_id)
    if perf.status=='crew_confirmed':raise HTTPException(409,'本场点名已确认，团体记录已冻结')
    if prod.forecast_state=='calculating':raise HTTPException(409,'预测重算进行中，团体补录请稍后重试')
    invalidate(s,prod)
    return perf,prod
def create(s,d,u):
    perf,prod=mutable_performance(s,d.performance_id)
    if s.scalar(select(GroupBooking.id).where(GroupBooking.performance_id==perf.id,GroupBooking.group_name==d.group_name)):raise HTTPException(409,'该场已登记同名团体预订，请用变动调整人数')
    x=GroupBooking(performance_id=perf.id,group_name=d.group_name,note=d.note.strip(),created_by=u.email,created_at=now());s.add(x);s.flush()
    s.add(GroupBookingChange(booking_id=x.id,booked_count=d.booked_count,recorded_by=u.email,recorded_at=now()))
    audit(s,u,f'登记团体预订 {d.group_name}→场次#{perf.id}');s.flush();return booking_view(s,x)
def change(s,id,d,u):
    b=get(s,GroupBooking,id);mutable_performance(s,b.performance_id);b=locked(s,GroupBooking,id)
    s.add(GroupBookingChange(booking_id=b.id,booked_count=d.booked_count,recorded_by=u.email,recorded_at=now()))
    audit(s,u,f'团体预订变动 #{id}→{d.booked_count}人');s.flush();return booking_view(s,b)
def arrive(s,id,d,u):
    b=get(s,GroupBooking,id);perf,prod=mutable_performance(s,b.performance_id);b=locked(s,GroupBooking,id)
    if perf.arrivals is None:raise HTTPException(409,'本场总验票尚未登记，先核对验票再登记团体实到')
    others=actual_sum(s,perf.id)-(b.actual_count or 0)
    if others+d.actual_count>perf.arrivals:raise HTTPException(409,f'团体实到合计 {others+d.actual_count} 人将超过总验票 {perf.arrivals} 人，对账不通过')
    b.actual_count=d.actual_count;b.actual_recorded_at=now();b.actual_recorded_by=u.email
    audit(s,u,f'团体实到登记 #{id}→{d.actual_count}人');s.flush();return booking_view(s,b)
