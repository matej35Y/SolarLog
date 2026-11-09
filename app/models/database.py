from sqlalchemy.exc import IntegrityError
from app.models.insforge_client import execute_sql
import uuid
from datetime import date, datetime

class Base:
    pass

class HourlyPrice:
    __tablename__ = 'hourly_prices'
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', str(uuid.uuid4()))
        
        # Convert string dates to datetime.date objects if needed
        dt = kwargs.get('date')
        if isinstance(dt, str):
            # Postgres returns '2023-01-01T00:00:00.000Z'
            if 'T' in dt:
                dt = dt.split('T')[0]
            dt = datetime.strptime(dt, '%Y-%m-%d').date()
        self.date = dt
        
        self.hour = kwargs.get('hour')
        self.price = kwargs.get('price')
        self.source = kwargs.get('source', 'hupx')
        
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.strftime('%Y-%m-%d') if hasattr(self.date, 'strftime') else self.date,
            'hour': self.hour,
            'price': self.price,
            'source': self.source
        }

class EnergyGeneration:
    __tablename__ = 'energy_generation'
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', str(uuid.uuid4()))
        
        dt = kwargs.get('date')
        if isinstance(dt, str):
            if 'T' in dt:
                dt = dt.split('T')[0]
            dt = datetime.strptime(dt, '%Y-%m-%d').date()
        self.date = dt
        
        self.hour = kwargs.get('hour')
        self.energy_kwh = kwargs.get('energy_kwh')
        
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.strftime('%Y-%m-%d') if hasattr(self.date, 'strftime') else self.date,
            'hour': self.hour,
            'energy_kwh': self.energy_kwh
        }

class MockQuery:
    def __init__(self, model_class_or_attr, session):
        self.model = model_class_or_attr
        self.session = session
        self.filters = []
        
        # If querying specific column like EnergyGeneration.date
        self.is_distinct = False
        self.query_column = None
        if hasattr(model_class_or_attr, 'class_') and hasattr(model_class_or_attr, 'key'):
            self.model = model_class_or_attr.class_
            self.query_column = model_class_or_attr.key
            
    def filter(self, condition):
        self.filters.append(condition)
        return self
        
    def filter_by(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(v, 'strftime'):
                v = v.strftime('%Y-%m-%d')
            if isinstance(v, str):
                self.filters.append(f"{k} = '{v}'")
            elif v is None:
                self.filters.append(f"{k} IS NULL")
            else:
                self.filters.append(f"{k} = {v}")
        return self
        
    def distinct(self):
        self.is_distinct = True
        return self
        
    def _build_where(self):
        if not self.filters:
            return ""
            
        where_clauses = []
        for f in self.filters:
            if hasattr(f, 'left') and hasattr(f, 'right'):
                # Handle mocked SQLAlchemy binary expression
                val = f.right.value
                col = f.left.key
                op = "=" if f.operator.__name__ == 'eq' else f.operator.__name__
                if hasattr(val, 'strftime'):
                    val = val.strftime('%Y-%m-%d')
                
                if isinstance(val, str):
                    where_clauses.append(f"{col} = '{val}'")
                elif val is None:
                    where_clauses.append(f"{col} IS NULL")
                else:
                    where_clauses.append(f"{col} = {val}")
            elif isinstance(f, str):
                where_clauses.append(f)
                
        return " WHERE " + " AND ".join(where_clauses)
        
    def all(self):
        table = self.model.__tablename__
        
        if self.is_distinct and self.query_column:
            query = f"SELECT DISTINCT {self.query_column} FROM {table}"
            query += self._build_where()
            rows = execute_sql(query)
            # Returns list of tuples
            return [(r[self.query_column],) for r in rows if self.query_column in r]
            
        elif self.query_column:
            query = f"SELECT {self.query_column} FROM {table}"
            query += self._build_where()
            rows = execute_sql(query)
            return [(r[self.query_column],) for r in rows if self.query_column in r]
            
        else:
            query = f"SELECT * FROM {table}"
            query += self._build_where()
            rows = execute_sql(query)
            return [self.model(**r) for r in rows]
            
    def first(self):
        res = self.all()
        return res[0] if res else None
        
    def count(self):
        table = self.model.__tablename__
        query = f"SELECT COUNT(*) as count FROM {table}"
        query += self._build_where()
        rows = execute_sql(query)
        if rows and 'count' in rows[0]:
            return int(rows[0]['count'])
        return 0

class MockBinaryExpression:
    def __init__(self, left, right, operator):
        self.left = left
        self.right = right
        self.operator = operator

def mock_eq(self, other):
    class MockRight:
        def __init__(self, value):
            self.value = value
    
    def eq(): pass
    
    return MockBinaryExpression(self, MockRight(other), eq)

# Mock column attributes for filter operations
# In a real app we'd intercept the class creation, but here we can just monkey patch
# the fields used in queries.
class MockColumn:
    def __init__(self, class_, key):
        self.class_ = class_
        self.key = key
        
    def __eq__(self, other):
        return mock_eq(self, other)

HourlyPrice.date = MockColumn(HourlyPrice, 'date')
HourlyPrice.source = MockColumn(HourlyPrice, 'source')
EnergyGeneration.date = MockColumn(EnergyGeneration, 'date')

class MockSession:
    def __init__(self):
        self._pending_adds = []
        
    def query(self, model_class):
        return MockQuery(model_class, self)
        
    def add(self, instance):
        self._pending_adds.append(instance)
        
    def commit(self):
        if not self._pending_adds:
            return
            
        for instance in self._pending_adds:
            table = instance.__tablename__
            data = instance.to_dict()
            
            columns = ", ".join(data.keys())
            values = []
            for v in data.values():
                if isinstance(v, str):
                    values.append(f"'{v}'")
                elif v is None:
                    values.append("NULL")
                else:
                    values.append(str(v))
                    
            vals_str = ", ".join(values)
            query = f"INSERT INTO {table} ({columns}) VALUES ({vals_str})"
            
            try:
                execute_sql(query)
            except Exception as e:
                # Catch integrity errors (e.g. duplicate key)
                if 'duplicate key' in str(e).lower() or 'unique constraint' in str(e).lower():
                    raise IntegrityError("Unique constraint violation", params={}, orig=e)
                raise
                
        self._pending_adds = []
        
    def rollback(self):
        self._pending_adds = []

session = MockSession()