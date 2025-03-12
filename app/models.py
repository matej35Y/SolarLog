from sqlalchemy import create_engine, Column, Integer, String, Float, Date, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class HourlyPrice(Base):
    __tablename__ = 'hourly_prices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    hour = Column(String, nullable=False)
    price = Column(Float, nullable=False)

class EnergyGeneration(Base):
    __tablename__ = 'energy_generation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    hour = Column(String, nullable=False)  # In format 'H1', 'H2', etc. to match price data
    energy_kwh = Column(Float, nullable=False)

    # Add a unique constraint to prevent duplicates
    __table_args__ = (
        UniqueConstraint('date', 'hour', name='_date_hour_uc'),
    )

# Create an SQLite database
engine = create_engine('sqlite:///hupx_prices.db')
Base.metadata.create_all(engine)

# Create a session
Session = sessionmaker(bind=engine)
session = Session() 