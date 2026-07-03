from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///metro_apteka.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    address = db.Column(db.String(300))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    manufacturer = db.Column(db.String(200))
    unit = db.Column(db.String(50), default='tablet')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    batch_number = db.Column(db.String(100))
    box_count = db.Column(db.Integer, nullable=False, default=0)
    units_per_box = db.Column(db.Integer, nullable=False, default=1)
    loose_units = db.Column(db.Integer, nullable=False, default=0)
    expiry_date = db.Column(db.Date)
    unit_price = db.Column(db.Numeric(10,2))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def total_units(self):
        return (self.box_count or 0) * (self.units_per_box or 1) + (self.loose_units or 0)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='pharmacist')
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    is_superadmin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class AdministrationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_name = db.Column(db.String(200), nullable=True)
    patient_id = db.Column(db.String(100), nullable=True)
    boxes_used = db.Column(db.Integer, nullable=False, default=0)
    units_used = db.Column(db.Integer, nullable=False, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    remaining_box_count = db.Column(db.Integer, nullable=False)
    remaining_loose_units = db.Column(db.Integer, nullable=False)

# Login loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helpers
def is_super():
    return current_user.is_authenticated and current_user.is_superadmin

def require_company_access(company_id):
    if is_super():
        return True
    if not current_user.is_authenticated or current_user.company_id != company_id:
        flash("Sizda ushbu kompaniyaga kirish ruxsati yo'q", 'danger')
        return False
    return True

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Tizimga muvaffaqiyatli kirdingiz', 'success')
            return redirect(url_for('dashboard'))
        flash('Noto`g`ri login yoki parol', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Chiqish amalga oshirildi', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if is_super():
        companies = Company.query.all()
        return render_template('dashboard.html', companies=companies)
    else:
        company = Company.query.get(current_user.company_id)
        return redirect(url_for('company_inventory', company_id=company.id))

@app.route('/companies')
@login_required
def companies():
    if not is_super():
        flash('Faqat adminga ruxsat', 'danger')
        return redirect(url_for('dashboard'))
    companies = Company.query.all()
    return render_template('companies.html', companies=companies)

@app.route('/companies/new', methods=['GET','POST'])
@login_required
def company_new():
    if not is_super():
        flash('Faqat adminga ruxsat', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form['name']
        c = Company(name=name)
        db.session.add(c)
        db.session.commit()
        flash('Korxona qo`shildi', 'success')
        return redirect(url_for('companies'))
    return render_template('company_new.html')

@app.route('/companies/<int:company_id>/inventory')
@login_required
def company_inventory(company_id):
    if not require_company_access(company_id):
        return redirect(url_for('dashboard'))
    inventories = Inventory.query.filter_by(company_id=company_id).all()
    # Group by medicine for totals
    totals = {}
    for inv in inventories:
        key = inv.medicine_id
        totals.setdefault(key, 0)
        totals[key] += inv.total_units
    medicines = {m.id: m for m in Medicine.query.filter(Medicine.id.in_([i.medicine_id for i in inventories])).all()} if inventories else {}
    return render_template('company_inventory.html', inventories=inventories, medicines=medicines, totals=totals, company=Company.query.get(company_id))

@app.route('/companies/<int:company_id>/inventory/new', methods=['GET','POST'])
@login_required
def inventory_new(company_id):
    if not require_company_access(company_id):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        med_name = request.form['medicine_name']
        med = Medicine.query.filter_by(name=med_name).first()
        if not med:
            med = Medicine(name=med_name)
            db.session.add(med)
            db.session.flush()
        batch = request.form.get('batch_number')
        box_count = int(request.form.get('box_count', 0) or 0)
        units_per_box = int(request.form.get('units_per_box', 1) or 1)
        loose = int(request.form.get('loose_units', 0) or 0)
        expiry = request.form.get('expiry_date')
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date() if expiry else None
        inv = Inventory(company_id=company_id, medicine_id=med.id, batch_number=batch,
                        box_count=box_count, units_per_box=units_per_box, loose_units=loose, expiry_date=expiry_date)
        db.session.add(inv)
        db.session.commit()
        flash('Inventory yozuvi qo`shildi', 'success')
        return redirect(url_for('company_inventory', company_id=company_id))
    return render_template('inventory_new.html', company=Company.query.get(company_id))

@app.route('/use', methods=['POST'])
@login_required
def use_med():
    # Use medicine from a specific inventory or auto (FEFO)
    inv_id = request.form.get('inventory_id')
    company_id = int(request.form.get('company_id'))
    if not require_company_access(company_id):
        return redirect(url_for('dashboard'))
    boxes_used = int(request.form.get('boxes_used', 0) or 0)
    units_used = int(request.form.get('units_used', 0) or 0)
    patient_name = request.form.get('patient_name')
    patient_id = request.form.get('patient_id')
    notes = request.form.get('notes')

    total_needed = 0
    # if inventory_id provided -> single batch
    if inv_id:
        inv = Inventory.query.get(int(inv_id))
        if inv.company_id != company_id:
            flash('Xato inventory', 'danger')
            return redirect(url_for('company_inventory', company_id=company_id))
        total_needed = boxes_used * inv.units_per_box + units_used
        if inv.total_units < total_needed:
            flash('Yetarli zaxira yo`q', 'danger')
            return redirect(url_for('company_inventory', company_id=company_id))
        # consume: prefer loose_units then open boxes
        need = total_needed
        # use loose units first
        use_loose = min(inv.loose_units, need)
        inv.loose_units -= use_loose
        need -= use_loose
        # convert boxes to loose if needed
        while need > 0 and inv.box_count > 0:
            # open one box
            inv.box_count -= 1
            inv.loose_units += inv.units_per_box
            # then take from loose
            take = min(inv.loose_units, need)
            inv.loose_units -= take
            need -= take
        if need > 0:
            flash('Yetarli zaxira yo`q (batch bo`yicha)', 'danger')
            db.session.rollback()
            return redirect(url_for('company_inventory', company_id=company_id))
        # log remaining
        log = AdministrationLog(inventory_id=inv.id, company_id=company_id, medicine_id=inv.medicine_id,
                                user_id=current_user.id, patient_name=patient_name, patient_id=patient_id,
                                boxes_used=boxes_used, units_used=units_used, notes=notes,
                                remaining_box_count=inv.box_count, remaining_loose_units=inv.loose_units)
        db.session.add(log)
        db.session.commit()
        flash('Dori ishlatildi va yozildi', 'success')
        return redirect(url_for('company_inventory', company_id=company_id))
    else:
        # Auto FEFO across batches for the company and medicine (medicine_name provided)
        med_name = request.form.get('medicine_name')
        med = Medicine.query.filter_by(name=med_name).first()
        if not med:
            flash('Dori topilmadi', 'danger')
            return redirect(url_for('company_inventory', company_id=company_id))
        inventories = Inventory.query.filter_by(company_id=company_id, medicine_id=med.id).order_by(Inventory.expiry_date.asc().nulls_last()).all()
        total_needed = boxes_used * (inventories[0].units_per_box if inventories else 1) + units_used
        need = total_needed
        for inv in inventories:
            if need <= 0:
                break
            avail = inv.total_units
            take = min(avail, need)
            # take from loose first
            use_loose = min(inv.loose_units, take)
            inv.loose_units -= use_loose
            remaining_take = take - use_loose
            # open boxes as needed
            while remaining_take > 0 and inv.box_count > 0:
                inv.box_count -= 1
                inv.loose_units += inv.units_per_box
                take_from_loose = min(inv.loose_units, remaining_take)
                inv.loose_units -= take_from_loose
                remaining_take -= take_from_loose
            # record a log per batch
            taken_boxes = 0
            taken_units = take
            log = AdministrationLog(inventory_id=inv.id, company_id=company_id, medicine_id=inv.medicine_id,
                                    user_id=current_user.id, patient_name=patient_name, patient_id=patient_id,
                                    boxes_used=taken_boxes, units_used=taken_units, notes=notes,
                                    remaining_box_count=inv.box_count, remaining_loose_units=inv.loose_units)
            db.session.add(log)
            need -= take
        if need > 0:
            db.session.rollback()
            flash('Yetarli zaxira yo`q (umumiy)', 'danger')
            return redirect(url_for('company_inventory', company_id=company_id))
        db.session.commit()
        flash('Dori avtomatik ravishda ishlatildi va yozildi', 'success')
        return redirect(url_for('company_inventory', company_id=company_id))

# Simple report
@app.route('/companies/<int:company_id>/logs')
@login_required
def company_logs(company_id):
    if not require_company_access(company_id):
        return redirect(url_for('dashboard'))
    logs = AdministrationLog.query.filter_by(company_id=company_id).order_by(AdministrationLog.timestamp.desc()).limit(200).all()
    return render_template('logs.html', logs=logs, company=Company.query.get(company_id))

# Seed sample data
def seed_data():
    if User.query.first():
        return
    # create companies
    c1 = Company(name='Metro Apteka Markaz')
    c2 = Company(name='Metro Apteka Chorsu')
    db.session.add_all([c1, c2])
    db.session.flush()
    # medicines
    m1 = Medicine(name='Analgin', manufacturer='FarmCo', unit='tablet')
    m2 = Medicine(name='Panadol', manufacturer='HealthLtd', unit='tablet')
    db.session.add_all([m1, m2])
    db.session.flush()
    # inventories
    inv1 = Inventory(company_id=c1.id, medicine_id=m1.id, batch_number='B-001', box_count=10, units_per_box=10, loose_units=5, expiry_date=date.today()+timedelta(days=365))
    inv2 = Inventory(company_id=c1.id, medicine_id=m2.id, batch_number='P-001', box_count=5, units_per_box=10, loose_units=0, expiry_date=date.today()+timedelta(days=180))
    inv3 = Inventory(company_id=c2.id, medicine_id=m1.id, batch_number='B-002', box_count=3, units_per_box=10, loose_units=2, expiry_date=date.today()+timedelta(days=90))
    db.session.add_all([inv1, inv2, inv3])
    # users
    admin = User(username='admin', is_superadmin=True)
    admin.set_password('admin123')
    user1 = User(username='metro1', company_id=c1.id)
    user1.set_password('pass123')
    user2 = User(username='metro2', company_id=c2.id)
    user2.set_password('pass123')
    db.session.add_all([admin, user1, user2])
    db.session.commit()

# Initialize DB
with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True)
