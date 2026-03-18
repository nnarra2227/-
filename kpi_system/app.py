from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Department, KPI, KPIResult
from datetime import datetime
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kpi-health-center-secret-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kpi_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول للوصول إلى هذه الصفحة'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── Auth Routes ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username, is_active=True).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('login'))

# ─── Dashboard ──────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    current_year = datetime.now().year
    current_month = datetime.now().month

    # Use 2025 data if current year has no data
    display_year = current_year
    if KPIResult.query.filter_by(year=current_year).count() == 0:
        display_year = 2025

    total_kpis = KPI.query.filter_by(is_active=True).count()
    departments = Department.query.filter_by(is_active=True).all()

    # KPIs by department
    dept_stats = []
    for dept in departments:
        kpi_count = KPI.query.filter_by(department_id=dept.id, is_active=True).count()
        if kpi_count > 0:
            dept_stats.append({'name': dept.name, 'count': kpi_count})

    # Recent results for achievement calculation
    results = KPIResult.query.filter_by(year=display_year).all()
    achieved = sum(1 for r in results if r.is_achieved() is True)
    not_achieved = sum(1 for r in results if r.is_achieved() is False)

    # Monthly trend data (last 12 months)
    trend_data = []
    for m in range(1, 13):
        month_results = KPIResult.query.filter_by(year=display_year, month=m).all()
        if month_results:
            ach = sum(1 for r in month_results if r.is_achieved() is True)
            total = len(month_results)
            pct = round((ach / total) * 100, 1) if total > 0 else 0
            trend_data.append({'month': m, 'achieved_pct': pct, 'total': total})

    # KPI type distribution
    type_counts = {}
    for kpi in KPI.query.filter_by(is_active=True).all():
        t = kpi.kpi_type or 'غير محدد'
        type_counts[t] = type_counts.get(t, 0) + 1

    # Latest entries
    latest_results = KPIResult.query.order_by(KPIResult.entered_at.desc()).limit(8).all()

    return render_template('dashboard.html',
        total_kpis=total_kpis,
        departments=departments,
        dept_stats=dept_stats,
        achieved=achieved,
        not_achieved=not_achieved,
        trend_data=json.dumps(trend_data),
        type_counts=json.dumps(type_counts),
        latest_results=latest_results,
        current_year=display_year
    )

# ─── KPI Management ─────────────────────────────────────────────────────────
@app.route('/kpis')
@login_required
def kpi_list():
    dept_filter = request.args.get('dept', '')
    type_filter = request.args.get('type', '')
    freq_filter = request.args.get('freq', '')
    search = request.args.get('search', '')

    query = KPI.query.filter_by(is_active=True)
    if dept_filter:
        query = query.filter_by(department_id=int(dept_filter))
    if type_filter:
        query = query.filter_by(kpi_type=type_filter)
    if freq_filter:
        query = query.filter_by(frequency=freq_filter)
    if search:
        query = query.filter(KPI.name.contains(search))

    kpis = query.order_by(KPI.department_id, KPI.id).all()
    departments = Department.query.filter_by(is_active=True).all()
    return render_template('kpi_list.html', kpis=kpis, departments=departments,
                           dept_filter=dept_filter, type_filter=type_filter,
                           freq_filter=freq_filter, search=search)

@app.route('/kpis/add', methods=['GET', 'POST'])
@login_required
def kpi_add():
    if current_user.role not in ['admin', 'quality']:
        flash('ليس لديك صلاحية لإضافة مؤشرات', 'danger')
        return redirect(url_for('kpi_list'))
    departments = Department.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        kpi = KPI(
            name=request.form['name'],
            department_id=request.form.get('department_id') or None,
            kpi_type=request.form['kpi_type'],
            target_value=float(request.form['target_value']) if request.form.get('target_value') else None,
            frequency=request.form['frequency'],
            responsible_person=request.form.get('responsible_person', ''),
            sample_type=request.form.get('sample_type', 'كاملة')
        )
        db.session.add(kpi)
        db.session.commit()
        flash('تم إضافة المؤشر بنجاح', 'success')
        return redirect(url_for('kpi_list'))
    return render_template('kpi_form.html', kpi=None, departments=departments, action='add')

@app.route('/kpis/edit/<int:kpi_id>', methods=['GET', 'POST'])
@login_required
def kpi_edit(kpi_id):
    if current_user.role not in ['admin', 'quality']:
        flash('ليس لديك صلاحية لتعديل المؤشرات', 'danger')
        return redirect(url_for('kpi_list'))
    kpi = KPI.query.get_or_404(kpi_id)
    departments = Department.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        kpi.name = request.form['name']
        kpi.department_id = request.form.get('department_id') or None
        kpi.kpi_type = request.form['kpi_type']
        kpi.target_value = float(request.form['target_value']) if request.form.get('target_value') else None
        kpi.frequency = request.form['frequency']
        kpi.responsible_person = request.form.get('responsible_person', '')
        kpi.sample_type = request.form.get('sample_type', 'كاملة')
        db.session.commit()
        flash('تم تحديث المؤشر بنجاح', 'success')
        return redirect(url_for('kpi_list'))
    return render_template('kpi_form.html', kpi=kpi, departments=departments, action='edit')

@app.route('/kpis/delete/<int:kpi_id>', methods=['POST'])
@login_required
def kpi_delete(kpi_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'غير مصرح'}), 403
    kpi = KPI.query.get_or_404(kpi_id)
    kpi.is_active = False
    db.session.commit()
    return jsonify({'success': True})

@app.route('/kpis/<int:kpi_id>')
@login_required
def kpi_detail(kpi_id):
    kpi = KPI.query.get_or_404(kpi_id)
    results = KPIResult.query.filter_by(kpi_id=kpi_id).order_by(
        KPIResult.year.desc(), KPIResult.quarter.desc(), KPIResult.month.desc()
    ).all()
    chart_data = []
    for r in reversed(results):
        label = ''
        if r.month:
            months_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                         'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
            label = f"{months_ar[r.month-1]} {r.year}"
        elif r.quarter:
            label = f"ر{r.quarter} {r.year}"
        else:
            label = str(r.year)
        if r.result_value is not None:
            chart_data.append({'label': label, 'value': r.result_value, 'target': r.target_value or kpi.target_value})
    return render_template('kpi_detail.html', kpi=kpi, results=results, chart_data=json.dumps(chart_data))

# ─── Data Entry ─────────────────────────────────────────────────────────────
@app.route('/data-entry', methods=['GET', 'POST'])
@login_required
def data_entry():
    departments = Department.query.filter_by(is_active=True).all()
    dept_id = request.args.get('dept_id', '')
    kpis = []
    if dept_id:
        kpis = KPI.query.filter_by(department_id=int(dept_id), is_active=True).all()
    elif current_user.department_id:
        kpis = KPI.query.filter_by(department_id=current_user.department_id, is_active=True).all()
        dept_id = str(current_user.department_id)

    if request.method == 'POST':
        kpi_id = int(request.form['kpi_id'])
        year = int(request.form['year'])
        month = request.form.get('month')
        quarter = request.form.get('quarter')
        result_val = request.form.get('result_value')
        target_val = request.form.get('target_value')

        # Check if result already exists
        existing = KPIResult.query.filter_by(
            kpi_id=kpi_id, year=year,
            month=int(month) if month else None,
            quarter=int(quarter) if quarter else None
        ).first()

        if existing:
            existing.sample_size = request.form.get('sample_size', '')
            existing.result_value = float(result_val) if result_val else None
            existing.target_value = float(target_val) if target_val else None
            existing.analysis = request.form.get('analysis', '')
            existing.corrective_action = request.form.get('corrective_action', '')
            existing.notes = request.form.get('notes', '')
            existing.entered_by = current_user.id
            existing.entered_at = datetime.utcnow()
            db.session.commit()
            flash('تم تحديث البيانات بنجاح', 'success')
        else:
            result = KPIResult(
                kpi_id=kpi_id,
                year=year,
                month=int(month) if month else None,
                quarter=int(quarter) if quarter else None,
                sample_size=request.form.get('sample_size', ''),
                result_value=float(result_val) if result_val else None,
                target_value=float(target_val) if target_val else None,
                analysis=request.form.get('analysis', ''),
                corrective_action=request.form.get('corrective_action', ''),
                notes=request.form.get('notes', ''),
                entered_by=current_user.id
            )
            db.session.add(result)
            db.session.commit()
            flash('تم حفظ البيانات بنجاح', 'success')
        return redirect(url_for('data_entry', dept_id=dept_id))

    return render_template('data_entry.html', departments=departments, kpis=kpis,
                           dept_id=dept_id, current_year=datetime.now().year)

@app.route('/api/kpi/<int:kpi_id>/info')
@login_required
def api_kpi_info(kpi_id):
    kpi = KPI.query.get_or_404(kpi_id)
    return jsonify({
        'id': kpi.id,
        'name': kpi.name,
        'frequency': kpi.frequency,
        'target_value': kpi.target_value,
        'kpi_type': kpi.kpi_type,
        'responsible_person': kpi.responsible_person
    })

# ─── Analysis ───────────────────────────────────────────────────────────────
@app.route('/analysis')
@login_required
def analysis():
    current_year = datetime.now().year
    # Default to 2025 if current year has no data
    default_year = current_year
    if KPIResult.query.filter_by(year=current_year).count() == 0:
        default_year = 2025
    year = int(request.args.get('year', default_year))
    departments = Department.query.filter_by(is_active=True).all()

    # Department performance
    dept_performance = []
    for dept in departments:
        kpis = KPI.query.filter_by(department_id=dept.id, is_active=True).all()
        if not kpis:
            continue
        achieved = 0
        not_achieved = 0
        for kpi in kpis:
            results = KPIResult.query.filter_by(kpi_id=kpi.id, year=year).all()
            for r in results:
                if r.is_achieved() is True:
                    achieved += 1
                elif r.is_achieved() is False:
                    not_achieved += 1
        total = achieved + not_achieved
        pct = round((achieved / total) * 100, 1) if total > 0 else 0
        dept_performance.append({
            'name': dept.name,
            'achieved': achieved,
            'not_achieved': not_achieved,
            'total': total,
            'pct': pct
        })

    # Quarterly comparison
    quarterly = []
    for q in range(1, 5):
        q_results = KPIResult.query.filter_by(year=year, quarter=q).all()
        ach = sum(1 for r in q_results if r.is_achieved() is True)
        total = len(q_results)
        quarterly.append({'quarter': q, 'achieved': ach, 'total': total,
                          'pct': round((ach/total)*100, 1) if total > 0 else 0})

    # Monthly trend
    monthly = []
    months_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                 'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
    for m in range(1, 13):
        m_results = KPIResult.query.filter_by(year=year, month=m).all()
        ach = sum(1 for r in m_results if r.is_achieved() is True)
        total = len(m_results)
        monthly.append({'month': months_ar[m-1], 'achieved': ach, 'total': total,
                        'pct': round((ach/total)*100, 1) if total > 0 else 0})

    return render_template('analysis.html',
        departments=departments,
        dept_performance=json.dumps(dept_performance),
        quarterly=json.dumps(quarterly),
        monthly=json.dumps(monthly),
        dept_performance_list=dept_performance,
        year=year,
        years=list(range(2023, current_year + 2))
    )

# ─── Reports ────────────────────────────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    departments = Department.query.filter_by(is_active=True).all()
    current_year = datetime.now().year
    return render_template('reports.html', departments=departments,
                           current_year=current_year,
                           years=list(range(2023, current_year + 2)))

@app.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    from report_generator import generate_pdf_report
    report_type = request.form.get('report_type')
    year = int(request.form.get('year', datetime.now().year))
    dept_id = request.form.get('dept_id')
    quarter = request.form.get('quarter')
    month = request.form.get('month')

    try:
        pdf_path = generate_pdf_report(report_type, year, dept_id, quarter, month)
        return send_file(pdf_path, as_attachment=True,
                         download_name=f'تقرير_مؤشرات_{year}.pdf',
                         mimetype='application/pdf')
    except Exception as e:
        flash(f'خطأ في إنشاء التقرير: {str(e)}', 'danger')
        return redirect(url_for('reports'))

# ─── User Management ────────────────────────────────────────────────────────
@app.route('/users')
@login_required
def user_list():
    if current_user.role != 'admin':
        flash('ليس لديك صلاحية للوصول', 'danger')
        return redirect(url_for('dashboard'))
    users = User.query.filter_by(is_active=True).all()
    departments = Department.query.filter_by(is_active=True).all()
    return render_template('user_list.html', users=users, departments=departments)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def user_add():
    if current_user.role != 'admin':
        flash('ليس لديك صلاحية', 'danger')
        return redirect(url_for('dashboard'))
    departments = Department.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('اسم المستخدم موجود مسبقاً', 'danger')
        else:
            user = User(
                username=request.form['username'],
                password=generate_password_hash(request.form['password']),
                full_name=request.form['full_name'],
                role=request.form['role'],
                department_id=request.form.get('department_id') or None
            )
            db.session.add(user)
            db.session.commit()
            flash('تم إضافة المستخدم بنجاح', 'success')
            return redirect(url_for('user_list'))
    return render_template('user_form.html', user=None, departments=departments, action='add')

@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def user_edit(user_id):
    if current_user.role != 'admin':
        flash('ليس لديك صلاحية', 'danger')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    departments = Department.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.role = request.form['role']
        user.department_id = request.form.get('department_id') or None
        if request.form.get('password'):
            user.password = generate_password_hash(request.form['password'])
        db.session.commit()
        flash('تم تحديث بيانات المستخدم', 'success')
        return redirect(url_for('user_list'))
    return render_template('user_form.html', user=user, departments=departments, action='edit')

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def user_delete(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'غير مصرح'}), 403
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'لا يمكن حذف حسابك الخاص'}), 400
    user.is_active = False
    db.session.commit()
    return jsonify({'success': True})

# ─── Department Management ──────────────────────────────────────────────────
@app.route('/departments')
@login_required
def dept_list():
    if current_user.role not in ['admin', 'quality']:
        flash('ليس لديك صلاحية', 'danger')
        return redirect(url_for('dashboard'))
    departments = Department.query.filter_by(is_active=True).all()
    return render_template('dept_list.html', departments=departments)

@app.route('/departments/add', methods=['POST'])
@login_required
def dept_add():
    if current_user.role not in ['admin', 'quality']:
        return jsonify({'error': 'غير مصرح'}), 403
    name = request.form.get('name', '').strip()
    if not name:
        flash('اسم القسم مطلوب', 'danger')
        return redirect(url_for('dept_list'))
    if Department.query.filter_by(name=name).first():
        flash('القسم موجود مسبقاً', 'warning')
        return redirect(url_for('dept_list'))
    dept = Department(name=name, description=request.form.get('description', ''))
    db.session.add(dept)
    db.session.commit()
    flash('تم إضافة القسم بنجاح', 'success')
    return redirect(url_for('dept_list'))

@app.route('/departments/delete/<int:dept_id>', methods=['POST'])
@login_required
def dept_delete(dept_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'غير مصرح'}), 403
    dept = Department.query.get_or_404(dept_id)
    dept.is_active = False
    db.session.commit()
    return jsonify({'success': True})

# ─── API for Charts ─────────────────────────────────────────────────────────
@app.route('/api/kpi/<int:kpi_id>/results')
@login_required
def api_kpi_results(kpi_id):
    year = request.args.get('year', datetime.now().year)
    results = KPIResult.query.filter_by(kpi_id=kpi_id, year=year).order_by(
        KPIResult.month, KPIResult.quarter).all()
    data = []
    months_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                 'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
    for r in results:
        label = months_ar[r.month-1] if r.month else f"ر{r.quarter}" if r.quarter else str(r.year)
        data.append({'label': label, 'value': r.result_value, 'target': r.target_value})
    return jsonify(data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                full_name='مدير النظام',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin / admin123")
    app.run(host='0.0.0.0', port=5000, debug=False)
