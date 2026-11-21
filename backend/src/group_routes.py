from fastapi import APIRouter,Depends
from sqlalchemy import select
from .db import db_session
from .auth import current,writers
from .group_models import GroupBooking
from .group_schemas import GroupBookingInput,GroupChangeInput,GroupArrivalInput
from . import group_service as groups
router=APIRouter()
@router.get('/group-bookings')
def list_bookings(s=Depends(db_session),u=Depends(current)):return [groups.booking_view(s,x) for x in s.scalars(select(GroupBooking).order_by(GroupBooking.id))]
@router.post('/group-bookings')
def create(d:GroupBookingInput,s=Depends(db_session),u=Depends(writers)):
    x=groups.create(s,d,u);s.commit();return x
@router.post('/group-bookings/{id}/changes')
def change(id:int,d:GroupChangeInput,s=Depends(db_session),u=Depends(writers)):
    x=groups.change(s,id,d,u);s.commit();return x
@router.post('/group-bookings/{id}/arrival')
def arrival(id:int,d:GroupArrivalInput,s=Depends(db_session),u=Depends(writers)):
    x=groups.arrive(s,id,d,u);s.commit();return x
