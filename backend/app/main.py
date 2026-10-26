from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal
import logging

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, Date, DateTime, String, Text, create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://todo:todo@localhost:5432/todo'
    cors_origins: str = 'http://localhost:5173'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


settings = Settings()
url = settings.database_url
if url.startswith(('postgres://', 'postgresql://')):
    url = 'postgresql+psycopg://' + url.split('://', 1)[1]
engine = create_engine(url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    priority: Mapped[str] = mapped_column(String(10), default='medium')
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TaskFields(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=5000)
    priority: Literal['low', 'medium', 'high'] = 'medium'
    due_date: date | None = None
    completed: bool = False

    @field_validator('title')
    @classmethod
    def title_required(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Title cannot be blank')
        return value


class TaskUpdate(TaskFields):
    # PATCH uses exclude_unset: omitted fields stay unchanged.
    title: str = Field(default='Untitled', min_length=1, max_length=200)


class TaskOut(TaskFields):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


def get_db():
    with SessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title='Daylist API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(',') if o.strip()], allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Content-Type'])


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logging.exception('Database operation failed', exc_info=exc)
    return JSONResponse(status_code=503, content={'detail': 'Database is temporarily unavailable. Please try again.'})


@app.get('/health')
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok'}


@app.get('/api/tasks', response_model=list[TaskOut])
def list_tasks(q: str = Query(default='', max_length=200), status: Literal['all', 'pending', 'completed'] = 'all', sort: Literal['newest', 'oldest'] = 'newest', db: Session = Depends(get_db)):
    statement = select(Task)
    if q.strip():
        statement = statement.where(Task.title.icontains(q.strip(), autoescape=True))
    if status != 'all':
        statement = statement.where(Task.completed == (status == 'completed'))
    statement = statement.order_by(Task.created_at.desc(), Task.id.desc()) if sort == 'newest' else statement.order_by(Task.created_at.asc(), Task.id.asc())
    return db.scalars(statement).all()


@app.post('/api/tasks', response_model=TaskOut, status_code=201)
def create_task(payload: TaskFields, db: Session = Depends(get_db)):
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def find_task(task_id, db):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, 'Task not found')
    return task


@app.patch('/api/tasks/{task_id}', response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = find_task(task_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


@app.delete('/api/tasks/{task_id}', status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db.delete(find_task(task_id, db))
    db.commit()
    return Response(status_code=204)
