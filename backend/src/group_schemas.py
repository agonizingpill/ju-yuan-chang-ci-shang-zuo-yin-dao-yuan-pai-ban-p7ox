from pydantic import BaseModel,Field,field_validator
class GroupBookingInput(BaseModel):
    performance_id:int
    group_name:str=Field(min_length=2,max_length=80)
    booked_count:int=Field(ge=0,le=3000)
    note:str=Field(default='',max_length=200)
    @field_validator('group_name')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():raise ValueError('团体名称不能为空')
        return v.strip()
class GroupChangeInput(BaseModel):
    booked_count:int=Field(ge=0,le=3000)
class GroupArrivalInput(BaseModel):
    actual_count:int=Field(ge=0,le=3000)
