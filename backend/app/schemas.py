from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class Profile(BaseModel):
    name: str = Field("", max_length=80)
    age: int | None = Field(None, ge=12, le=65)
    height: float | None = Field(None, ge=100, le=230)
    pre_weight: float | None = Field(None, ge=25, le=300)
    current_weight: float | None = Field(None, ge=25, le=300)
    lmp: date | None = None
    due_date: date | None = None
    conception_date: date | None = None
    doctor_weeks: int | None = Field(None, ge=0, le=43)
    doctor_days: int | None = Field(None, ge=0, le=6)
    doctor_date: date | None = None
    first_pregnancy: str = ""
    history: str = Field("", max_length=3000)
    chronic: str = Field("", max_length=3000)
    allergies: str = Field("", max_length=2000)
    blood_group: str = Field("", max_length=30)
    rh: str = Field("", max_length=30)
    medications: str = Field("", max_length=3000)
    supplements: str = Field("", max_length=3000)
    activity: str = Field("", max_length=500)
    frequency: int | None = Field(None, ge=0, le=14)
    training_history: str = Field("", max_length=2000)
    lifestyle: str = Field("", max_length=2000)
    completed: bool = False

    @field_validator("lmp", "conception_date", "doctor_date")
    @classmethod
    def not_future(cls, value):
        if value and value > date.today():
            raise ValueError("Дата не может быть в будущем")
        return value

    @model_validator(mode="after")
    def doctor_anchor(self):
        if self.doctor_weeks is not None and self.doctor_date is None:
            raise ValueError("Укажите дату определения срока врачом")
        return self


class RecordInput(BaseModel):
    kind: Literal[
        "weight",
        "blood_pressure",
        "lab",
        "ultrasound",
        "medication",
        "supplement",
        "symptom",
        "activity",
        "event",
        "note",
    ]
    title: str = Field("", max_length=200)
    value: float | None = Field(None, ge=0, le=1000000)
    secondary: float | None = Field(None, ge=0, le=1000)
    unit: str = Field("", max_length=50)
    notes: str = Field("", max_length=5000)
    recorded_at: datetime
    reference: str = Field("", max_length=200)

    @model_validator(mode="after")
    def check_values(self):
        if self.kind == "weight" and (
            self.value is None or not 25 <= self.value <= 300
        ):
            raise ValueError("Проверьте вес: укажите значение от 25 до 300 кг")
        if self.kind == "blood_pressure" and (
            self.value is None
            or self.secondary is None
            or not 50 <= self.value <= 280
            or not 30 <= self.secondary <= 180
            or self.secondary >= self.value
        ):
            raise ValueError("Проверьте верхнее и нижнее давление")
        if self.kind != "event" and self.recorded_at.date() > date.today():
            raise ValueError("Дата измерения не может быть в будущем")
        return self


class ChatInput(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    detail: bool = False


class SupportInput(BaseModel):
    category: Literal[
        "Проблема с оплатой",
        "Не загрузился анализ",
        "Проблема со входом",
        "Ошибка данных",
        "Другое",
    ]
    text: str = Field(min_length=3, max_length=5000)


class Confirmation(BaseModel):
    records: list[RecordInput] = Field(default_factory=list, max_length=100)
    profile_update: Profile | None = None


class AgentInput(BaseModel):
    price: int = Field(499, ge=1, le=100000)
    trial_days: int = Field(30, ge=0, le=365)
    trial_limit: int = Field(5, ge=0, le=1000)
    paid_limit: int = Field(20, ge=0, le=1000)
    max_tokens: int = Field(1200, ge=100, le=8000)
    temperature: float = Field(0.3, ge=0, le=1)
    timeout: int = Field(60, ge=5, le=120)
    model: str = Field("", max_length=100)
    fallback_model: str = Field("", max_length=100)
    vision_model: str = Field("", max_length=100)
    system_prompt: str = Field("", max_length=50000)
    features: dict[str, bool] = Field(default_factory=dict)
