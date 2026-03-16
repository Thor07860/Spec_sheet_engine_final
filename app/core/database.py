from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker , Session
from sqlalchemy.ext.declarative import declarative_base 
from typing import Generator 
from app.core.config import settings


#DATABASE ENGINE 
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True, #hEALTH cHECK bEFORE cONNECTION
    pool_size=10,   #no of connection in the pool
    max_overflow=20,   #extra connection allowed during traffic spikes
    pool_recycle=3600,   #recycle connections every 1 hour 
    echo=settings.DEBUG,
)


#SESSION FACTORY 
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

#Base Class 
Base = declarative_base()

#Database Dependency 
def get_db() -> Generator[Session, None , None]:
    db = SessionLocal()
    try : # Over here is hands over the db whoever calls the get_db function and once the request is done it will close the connection to prevent leaks
        yield db 
    finally:
        db.close()
#CREATE Tables on Startup 

def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
