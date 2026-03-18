"""
Script to seed the database with KPI data from the Excel file
and create sample users and results
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import User, Department, KPI, KPIResult
from werkzeug.security import generate_password_hash
import pandas as pd
from datetime import datetime
import random

EXCEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'upload', 'قائمةمؤشرات2025.xlsx')

def seed():
    with app.app_context():
        db.create_all()

        print("🌱 Seeding database...")

        # ── Users ────────────────────────────────────────────────
        users_data = [
            ('admin',   'admin123',   'مدير النظام',           'admin',   None),
            ('quality', 'quality123', 'نورة القربان',           'quality', 'قسم الجودة'),
            ('head1',   'head123',    'د. فيصل العتيبي',        'head',    'قسم الأسنان'),
            ('head2',   'head123',    'رئيس قسم التمريض',       'head',    'قسم التمريض'),
            ('staff1',  'staff123',   'فهد الدخيل',             'staff',   'تعزيز الصحة وتوعية المجتمع'),
            ('staff2',  'staff123',   'عادل الحسون',            'staff',   'المختبر'),
        ]

        # ── Departments from Excel ───────────────────────────────
        try:
            df = pd.read_excel(EXCEL_PATH, header=1)
            dept_names = df['القسم'].dropna().unique().tolist()
        except Exception as e:
            print(f"Warning: Could not read Excel: {e}")
            dept_names = []

        # Fallback departments
        default_depts = [
            'قسم الأسنان', 'عيادة التغذية', 'تعزيز الصحة وتوعية المجتمع',
            'عيادة المسنين', 'مكافحة العدوى', 'الطب الوقائي',
            'عيادة الأمراض المعدية', 'عيادة الموظفين', 'التعقيم',
            'قسم التمريض', 'قسم الطوارئ', 'عيادة الامراض المزمنة',
            'عيادة الطفل السليم', 'عيادة التطعيمات', 'عيادة الأمومة',
            'عيادات الطب العام', 'الامراض المزمنة', 'قسم الجودة',
            'الصيدلية', 'المختبر', 'الاشعة', 'علاقات المرضى',
            'الاحالات', 'علاقات الموظفين', 'قسم السلامة', 'قسم الصيانه'
        ]

        all_depts = list(set(dept_names + default_depts))

        dept_map = {}
        for name in all_depts:
            name = str(name).strip()
            if not name:
                continue
            existing = Department.query.filter_by(name=name).first()
            if not existing:
                dept = Department(name=name)
                db.session.add(dept)
                db.session.flush()
                dept_map[name] = dept.id
            else:
                dept_map[name] = existing.id

        db.session.commit()
        print(f"  ✓ {len(dept_map)} departments created")

        # ── Users ────────────────────────────────────────────────
        for username, password, full_name, role, dept_name in users_data:
            if not User.query.filter_by(username=username).first():
                dept_id = dept_map.get(dept_name) if dept_name else None
                user = User(
                    username=username,
                    password=generate_password_hash(password),
                    full_name=full_name,
                    role=role,
                    department_id=dept_id
                )
                db.session.add(user)

        db.session.commit()
        print(f"  ✓ Users created")

        # ── KPIs from Excel ──────────────────────────────────────
        type_normalize = {
            'بنية': 'بنية', 'مؤشر بنية': 'بنية',
            'عمليات': 'عمليات',
            'نتائج': 'نتائج', 'مخرجات': 'نتائج'
        }

        freq_normalize = {
            'شهري': 'شهري', 'ربع سنوي': 'ربع سنوي',
            'نصف سنوي': 'نصف سنوي', 'سنوي': 'سنوي'
        }

        kpi_map = {}  # name -> KPI object

        try:
            df = pd.read_excel(EXCEL_PATH, header=1)
            kpi_count = 0
            for _, row in df.iterrows():
                name = str(row.get('اسم المؤشر', '')).strip()
                if not name or name == 'nan':
                    continue

                kpi_type = type_normalize.get(str(row.get('نوعه', '')).strip(), 'نتائج')
                dept_name = str(row.get('القسم', '')).strip()
                dept_id = dept_map.get(dept_name) if dept_name and dept_name != 'nan' else None
                freq_raw = str(row.get('التكرار', '')).strip()
                frequency = freq_normalize.get(freq_raw, 'ربع سنوي')
                responsible = str(row.get('المسؤول', '')).strip()
                responsible = '' if responsible == 'nan' else responsible
                sample_type = str(row.get('حجم العينة', 'كاملة')).strip()
                sample_type = 'عشوائية' if 'عشوائية' in sample_type else 'كاملة'

                target_raw = row.get('المستهدف %', None)
                try:
                    target = float(target_raw) if target_raw and str(target_raw) not in ['nan', '—', ''] else None
                except:
                    target = None

                existing = KPI.query.filter_by(name=name).first()
                if not existing:
                    kpi = KPI(
                        name=name,
                        department_id=dept_id,
                        kpi_type=kpi_type,
                        target_value=target,
                        frequency=frequency,
                        responsible_person=responsible,
                        sample_type=sample_type
                    )
                    db.session.add(kpi)
                    db.session.flush()
                    kpi_map[name] = kpi
                    kpi_count += 1

                    # Add quarterly results from Excel
                    quarters_data = [
                        (row.get('الربع الاول %'), 1),
                        (row.get('الربع الثاني %'), 2),
                        (row.get('الربع الثالث% '), 3),
                        (row.get('الربع الرابع%'), 4),
                    ]

                    for q_val, q_num in quarters_data:
                        try:
                            val_str = str(q_val).strip()
                            if val_str in ['nan', '—', '', 'تقرير', 'ـــ']:
                                continue
                            val = float(val_str)
                            result = KPIResult(
                                kpi_id=kpi.id,
                                year=2025,
                                quarter=q_num,
                                result_value=val,
                                target_value=target,
                                analysis=str(row.get('تحليل النتائج ', '') or '').strip(),
                                notes=str(row.get('ملاحظات', '') or '').strip(),
                                entered_by=1
                            )
                            db.session.add(result)
                        except (ValueError, TypeError):
                            pass

            db.session.commit()
            print(f"  ✓ {kpi_count} KPIs loaded from Excel")

        except Exception as e:
            print(f"  ⚠ Error loading Excel: {e}")
            db.session.rollback()

        # ── Add some monthly sample data ─────────────────────────
        try:
            monthly_kpis = KPI.query.filter_by(frequency='شهري').all()
            admin_user = User.query.filter_by(username='admin').first()
            added = 0
            for kpi in monthly_kpis[:10]:
                for month in range(1, 13):
                    existing = KPIResult.query.filter_by(kpi_id=kpi.id, year=2025, month=month).first()
                    if not existing:
                        target = kpi.target_value or 100
                        if target == 0:
                            val = 0
                        else:
                            base = random.uniform(75, 100)
                            val = round(min(base, 100), 1)
                        result = KPIResult(
                            kpi_id=kpi.id,
                            year=2025,
                            month=month,
                            result_value=val,
                            target_value=target,
                            analysis='بيانات تجريبية',
                            entered_by=admin_user.id if admin_user else 1
                        )
                        db.session.add(result)
                        added += 1
            db.session.commit()
            print(f"  ✓ {added} monthly sample results added")
        except Exception as e:
            print(f"  ⚠ Error adding monthly data: {e}")
            db.session.rollback()

        # Summary
        print(f"\n✅ Database seeded successfully!")
        print(f"   Departments: {Department.query.count()}")
        print(f"   KPIs: {KPI.query.count()}")
        print(f"   Results: {KPIResult.query.count()}")
        print(f"   Users: {User.query.count()}")
        print(f"\n🔑 Login credentials:")
        print(f"   admin / admin123 (مدير النظام)")
        print(f"   quality / quality123 (قسم الجودة)")
        print(f"   head1 / head123 (رئيس قسم)")
        print(f"   staff1 / staff123 (موظف إدخال)")

if __name__ == '__main__':
    seed()
