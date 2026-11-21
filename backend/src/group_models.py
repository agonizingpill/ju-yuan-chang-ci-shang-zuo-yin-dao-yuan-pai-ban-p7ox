from sqlalchemy import String,Integer,ForeignKey,UniqueConstraint,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class GroupBooking(Base):
    __tablename__='group_bookings'
    __table_args__=(UniqueConstraint('performance_id','group_name'),CheckConstraint('actual_count IS NULL OR actual_count >= 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    performance_id:Mapped[int]=mapped_column(ForeignKey('performances.id'))
    group_name:Mapped[str]=mapped_column(String(80))
    note:Mapped[str]=mapped_column(String(200),default='')
    actual_count:Mapped[int|None]=mapped_column(Integer,nullable=True)
    actual_recorded_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    actual_recorded_by:Mapped[str|None]=mapped_column(String(100),nullable=True)
    created_by:Mapped[str]=mapped_column(String(100))
    created_at:Mapped[str]=mapped_column(String(40))
class GroupBookingChange(Base):
    __tablename__='group_booking_changes'
    __table_args__=(CheckConstraint('booked_count >= 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    booking_id:Mapped[int]=mapped_column(ForeignKey('group_bookings.id'))
    booked_count:Mapped[int]=mapped_column(Integer)
    recorded_by:Mapped[str]=mapped_column(String(100))
    recorded_at:Mapped[str]=mapped_column(String(40))
