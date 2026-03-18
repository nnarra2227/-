from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # admin, quality, head, staff
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    department = db.relationship('Department', backref='users')

    ROLES = {
        'admin': 'مدير النظام',
        'quality': 'قسم الجودة',
        'head': 'رئيس قسم',
        'staff': 'موظف إدخال بيانات'
    }

    def role_name(self):
        return self.ROLES.get(self.role, self.role)


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    kpis = db.relationship('KPI', backref='department', lazy=True)


class KPI(db.Model):
    __tablename__ = 'kpis'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    kpi_type = db.Column(db.String(50), nullable=False)  # بنية / عمليات / نتائج
    target_value = db.Column(db.Float, nullable=True)
    frequency = db.Column(db.String(50), nullable=False)  # شهري / ربع سنوي / نصف سنوي / سنوي
    responsible_person = db.Column(db.String(150))
    sample_type = db.Column(db.String(50))  # كاملة / عشوائية
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('KPIResult', backref='kpi', lazy=True, cascade='all, delete-orphan')


class KPIResult(db.Model):
    __tablename__ = 'kpi_results'
    id = db.Column(db.Integer, primary_key=True)
    kpi_id = db.Column(db.Integer, db.ForeignKey('kpis.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=True)   # 1-12 or None for quarterly
    quarter = db.Column(db.Integer, nullable=True)  # 1-4 or None for monthly
    sample_size = db.Column(db.String(100))
    result_value = db.Column(db.Float, nullable=True)
    target_value = db.Column(db.Float, nullable=True)
    analysis = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    notes = db.Column(db.Text)
    entered_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    entered_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='results')

    def is_achieved(self):
        if self.result_value is None or self.target_value is None:
            return None
        # For KPIs where target is 0 (like errors), achieved means result <= target
        if self.target_value == 0:
            return self.result_value <= self.target_value
        return self.result_value >= self.target_value
