# Core Flask
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

# Database
import psycopg2
import psycopg2.extras
from psycopg2 import sql
from flask_sqlalchemy import SQLAlchemy
import re

# Data Handling
import pandas as pd
from functools import wraps
from psycopg2 import IntegrityError

# Real-time
from flask_socketio import SocketIO

# Configuration
from dotenv import load_dotenv
import os

# Date/Time
from datetime import datetime, time


# Debugging
import traceback
import logging


# CORS
from flask_cors import CORS

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
CORS(app)

# Configuration
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key-please-change')


# Database configuration
db_config = {
    'dbname': 'railway',
    'user': 'postgres',
    'password': 'wuDgFAPkMstfrYjNHluOnyquQknRTzPq',
    'host': 'crossover.proxy.rlwy.net',
    'port': '17089'
}


# Build connection string
default_db_uri = (
    f"postgresql://{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
)

# Use DATABASE_URL environment variable if set, else fallback to built connection string
db_uri = os.getenv('DATABASE_URL', default_db_uri).replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 300,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# Database connection helper
def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error connecting to the database: {e}")
        return None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/test_db')
def test_db():
    try:
        db.session.execute('SELECT 1')
        return "✅ Database connection successful"
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return f"❌ Connection failed: {e}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Both email and password are required', 'danger')
            return render_template('login.html')
        
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute(
                sql.SQL("SELECT id, username, password, role, is_active FROM users WHERE email = %s"),
                [email]
            )
            user = cur.fetchone()
            
            if not user:
                flash('Invalid email or password', 'danger')
                return render_template('login.html')
                
            if not user[4]:  # is_active
                flash('Account is inactive. Please contact support.', 'warning')
                return render_template('login.html')
                
            if check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['email'] = email
                session['role'] = user[3]
                session['_fresh'] = True
                
                # Update last login
                try:
                    cur.execute(
                        sql.SQL("UPDATE users SET last_login = NOW() WHERE id = %s"),
                        [user[0]]
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to update last login: {e}")
                
                flash(f'Welcome back, {user[1]}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid email or password', 'danger')
        except Exception as e:
            if conn:
                conn.rollback()
            flash('An error occurred during login', 'danger')
            logger.error(f"Login error: {e}", exc_info=True)
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', '')
        
        # Validation
        errors = []
        
        if len(username) < 3:
            errors.append('Username must be at least 3 characters')
        elif len(username) > 50:
            errors.append('Username must be less than 50 characters')
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers and underscores')
            
        if not email:
            errors.append('Email is required')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Invalid email address')
        elif len(email) > 255:
            errors.append('Email must be less than 255 characters')
            
        if len(password) < 8:
            errors.append('Password must be at least 8 characters')
        elif len(password) > 128:
            errors.append('Password must be less than 128 characters')
        elif not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter')
        elif not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter')
        elif not re.search(r'[0-9]', password):
            errors.append('Password must contain at least one number')
            
        if password != confirm_password:
            errors.append('Passwords do not match')
            
        valid_roles = ['geotechnical_engineer', 'tailing_system_engineer', 'hydrological_engineer', 'admin']
        if not role or role not in valid_roles:
            errors.append('Please select a valid professional role')
            
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('register.html', 
                                username=username, 
                                email=email,
                                role=role)
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Check for existing user
            cur.execute(
                sql.SQL("SELECT id FROM users WHERE email = %s OR username = %s"),
                [email, username]
            )
            if cur.fetchone():
                flash('Email or username already exists', 'danger')
                return render_template('register.html',
                                    username=username,
                                    email=email,
                                    role=role)
                
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            
            cur.execute(
                sql.SQL("""
                    INSERT INTO users (
                        username, 
                        email, 
                        password, 
                        role, 
                        is_active, 
                        created_at
                    ) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """),
                [
                    username, 
                    email, 
                    hashed_password, 
                    role, 
                    True,
                    datetime.now()
                ]
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            flash('Registration failed. Please try again.', 'danger')
            logger.error(f"Registration error for {email}: {e}", exc_info=True)
            return render_template('register.html',
                                username=username,
                                email=email,
                                role=role)
        finally:
            cur.close()
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/index')
@login_required
def index():
    return render_template('index.html')

@app.route('/dams')
@login_required
def dams():
    return render_template('dams.html')

def fetch_dam_data():
    """Fetch dam data from the database and return as JSON."""
    conn = get_db_connection()
    if not conn:
        return {'error': 'Database connection failed.'}
    
    try:
        query = """
            SELECT 
                sites, 
                total_capacity, 
                stock_volume, 
                partial_capacity, 
                global_fill_rate, 
                partial_fill_rate, 
                total_autonomy, 
                partial_autonomy,
                stockage_ratio,
                capex_2022, 
                capex_2023, 
                capex_2024, 
                capex_2025, 
                capex_2026, 
                capex_2027, 
                capex_2028, 
                capex_2029, 
                capex_2030,
                total_remaining_capacity,
                production_rate,
                long_term_situation,
                short_term_situation,
                total_capex
            FROM managem_dams;
        """
        df = pd.read_sql(query, conn)
        
        # Replace NaN values with None (which becomes null in JSON)
        df = df.where(pd.notnull(df), None)

        # Convert date fields to string if necessary
        date_fields = ['commission_date', 'complete_full_date', 'stop_definitive_date', 'date_of_actualisation']
        for field in date_fields:
            if field in df.columns:
                df[field] = df[field].astype(str)

        return df.to_dict(orient='records')
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return {'error': 'Failed to fetch data from the database.'}
    finally:
        conn.close()

@socketio.on('connect')
def handle_connect():
    """Send the initial data when a client connects."""
    data = fetch_dam_data()
    socketio.emit('update_data', data)

@app.route('/daily', methods=['GET', 'POST'])
@login_required
def daily():
    if request.method == 'POST':
        try:
            # Required fields
            sites = request.form['sites']
            total_capacity = float(request.form['total_capacity'])
            stock_volume = float(request.form['stock_volume'])
            ready_capacity = float(request.form['ready_capacity'])
            production_rate = float(request.form['production_rate'])
            partial_capacity = float(request.form['partial_capacity'])
            date_of_actualisation = request.form['date_of_actualisation']

            # Optional fields
            optional_fields = [
                'long_term_situation',
                'short_term_situation',
                'commission_date',
                'complete_full_date',
                'stop_definitive_date',
                'comments',
                'capex_2022',
                'capex_2023',
                'capex_2024',
                'capex_2025',
                'capex_2026',
                'capex_2027',
                'capex_2028',
                'capex_2029',
                'capex_2030',
                'total_autonomy'
            ]

            data = {
                'sites': sites,
                'total_capacity': total_capacity,
                'stock_volume': stock_volume,
                'ready_capacity': ready_capacity,
                'production_rate': production_rate,
                'partial_capacity': partial_capacity,
                'date_of_actualisation': date_of_actualisation
            }

            # Establish database connection
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed.")
                
            cur = conn.cursor()

            # Fetch the most recent entry for the site
            cur.execute('''
                SELECT * FROM managem_dams
                WHERE sites = %s
                ORDER BY date_of_actualisation DESC
                LIMIT 1
            ''', (sites,))
            last_entry = cur.fetchone()
            columns = [desc[0] for desc in cur.description] if cur.description else []

            # Collect optional fields
            for field in optional_fields:
                value = request.form.get(field)
                if value in (None, ''):
                    if last_entry and field in columns:
                        value = last_entry[columns.index(field)]
                    else:
                        value = None
                else:
                    if field in ['commission_date', 'complete_full_date', 'stop_definitive_date']:
                        value = value
                    elif 'capex' in field or field == 'total_autonomy':
                        try:
                            value = float(value)
                        except ValueError:
                            value = None
                    else:
                        value = value

                data[field] = value

            # Build the INSERT query
            insert_columns = [k for k, v in data.items() if v is not None]
            insert_values = [data[col] for col in insert_columns]

            insert_query = sql.SQL('''
                INSERT INTO managem_dams ({fields})
                VALUES ({values})
            ''').format(
                fields=sql.SQL(', ').join(map(sql.Identifier, insert_columns)),
                values=sql.SQL(', ').join(sql.Placeholder() * len(insert_values))
            )

            cur.execute(insert_query, insert_values)
            conn.commit()

            # Emit updated data to all connected clients
            socketio.emit('update_data', fetch_dam_data())

            flash('Data saved successfully!', 'success')
            return redirect(url_for('daily'))

        except ValueError as e:
            flash(f"Invalid input: {e}", 'danger')
            return redirect(url_for('daily'))
        except Exception as e:
            logger.error(f"Error inserting data: {e}", exc_info=True)
            flash(f"An error occurred: {e}", 'danger')
            return redirect(url_for('daily'))
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

    # For GET request, render the form
    return render_template('daily.html')

@app.route('/get_previous_data/<site>')
@login_required
def get_previous_data(site):
    """Fetch the most recent data for the specified site."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
        
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT 
                long_term_situation,
                short_term_situation,
                commission_date,
                complete_full_date,
                stop_definitive_date,
                comments,
                capex_2022,
                capex_2023,
                capex_2024,
                capex_2025,
                capex_2026,
                capex_2027,
                capex_2028,
                capex_2029,
                capex_2030,
                total_autonomy
            FROM managem_dams
            WHERE sites = %s
            ORDER BY date_of_actualisation DESC
            LIMIT 1
        ''', (site,))
        
        row = cur.fetchone()
        if not row:
            return jsonify({})
            
        columns = [desc[0] for desc in cur.description]
        data = dict(zip(columns, row))
        
        # Convert date fields to string if necessary
        date_fields = ['commission_date', 'complete_full_date', 'stop_definitive_date']
        for field in date_fields:
            if data.get(field) and isinstance(data[field], (datetime.date, datetime.datetime)):
                data[field] = data[field].strftime('%Y-%m-%d')
                
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching previous data: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

@app.route('/geotechnical')
@login_required
@role_required(['geotechnical_engineer', 'admin'])
def geotechnical():
    return render_template('geotechnical.html')

@app.route('/weekly')
@login_required
def weekly():
    return render_template('weekly.html')

@app.route('/monthly', methods=['GET', 'POST'])
@login_required
def monthly():
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed', 'danger')
        return render_template('monthly.html', records=[])
        
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'create':
                annee = request.form['annee']
                precipitation = request.form['precipitation_mm']
                if not annee or not precipitation:
                    flash('Both Year and Precipitation are required!', 'danger')
                else:
                    try:
                        cur.execute(
                            'INSERT INTO climate_data (annee, precipitation_mm) VALUES (%s, %s)',
                            (annee, precipitation)
                        )
                        conn.commit()
                        flash('Record created successfully!', 'success')
                    except IntegrityError:
                        conn.rollback()
                        flash('Year already exists!', 'danger')
                    except Exception as e:
                        conn.rollback()
                        flash(f'Error creating record: {e}', 'danger')
            
            elif action == 'edit':
                annee = request.form['annee']
                precipitation = request.form['precipitation_mm']
                if not precipitation:
                    flash('Precipitation is required!', 'danger')
                else:
                    try:
                        cur.execute(
                            'UPDATE climate_data SET precipitation_mm = %s WHERE annee = %s',
                            (precipitation, annee)
                        )
                        if cur.rowcount == 0:
                            flash('No record found to update!', 'warning')
                        else:
                            conn.commit()
                            flash('Record updated successfully!', 'success')
                    except Exception as e:
                        conn.rollback()
                        flash(f'Error updating record: {e}', 'danger')
            
            elif action == 'delete':
                annee = request.form['annee']
                try:
                    cur.execute('DELETE FROM climate_data WHERE annee=%s', (annee,))
                    if cur.rowcount == 0:
                        flash('No record found to delete!', 'warning')
                    else:
                        conn.commit()
                        flash('Record deleted successfully!', 'success')
                except Exception as e:
                    conn.rollback()
                    flash(f'Error deleting record: {e}', 'danger')
        
        # Fetch all records for display and charting
        cur.execute("SELECT * FROM climate_data ORDER BY annee")
        records = cur.fetchall()
        return render_template('monthly.html', records=records)
        
    except Exception as e:
        logger.error(f"Error in monthly route: {e}", exc_info=True)
        flash(f'An error occurred: {e}', 'danger')
        return render_template('monthly.html', records=[])
    finally:
        cur.close()
        conn.close()

@app.route('/yearly')
@login_required
def yearly():
    return render_template('yearly.html')

@app.route('/environmental')
@login_required
def environmental():
    return render_template('environmental.html')

@app.route('/rmr')
@login_required
def rmr():
    return render_template('rmr.html')

def fetch_density_data(site_filter=None):
    """Fetch all records from the density_controle table."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """
            SELECT date, time, zone_tailing_system, measured_density, targeted_density,
                   difference, corrective_action, operator, comments, sites
            FROM density_controle
        """
        params = []
        
        if site_filter:
            query += " WHERE sites = %s"
            params.append(site_filter)
            
        query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(query, tuple(params))
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching density data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

@app.route('/density', methods=['GET', 'POST'])
@login_required
def density():
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['date', 'time', 'zone_tailing_system', 'measured_density', 
                             'targeted_density', 'operator', 'sites']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f"{field.replace('_', ' ').title()} is required", 'danger')
                    return redirect(url_for('density'))

            date = request.form['date']
            time_val = request.form['time']
            zone_tailing_system = request.form['zone_tailing_system']
            measured_density = float(request.form['measured_density'])
            targeted_density = float(request.form['targeted_density'])
            corrective_action = request.form.get('corrective_action', '')
            operator = request.form['operator']
            comments = request.form.get('comments', '')
            sites = request.form['sites']

            # Connect to the database
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed.")
                
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # Insert the record (database will calculate difference)
            insert_query = """
                INSERT INTO density_controle 
                (date, time, zone_tailing_system, measured_density, targeted_density,
                 corrective_action, operator, comments, sites)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
            """
            cur.execute(insert_query, (
                date, time_val, zone_tailing_system, measured_density, targeted_density,
                corrective_action, operator, comments, sites
            ))

            # Commit the transaction
            new_record = cur.fetchone()
            conn.commit()
            
            # Format the new record for the response
            new_record_dict = {
                'date': new_record['date'].strftime('%Y-%m-%d') if new_record['date'] else '',
                'time': new_record['time'].strftime('%H:%M:%S') if new_record['time'] else '',
                'zone_tailing_system': new_record['zone_tailing_system'],
                'measured_density': float(new_record['measured_density']),
                'targeted_density': float(new_record['targeted_density']),
                'difference': float(new_record['difference']) if new_record['difference'] else None,
                'corrective_action': new_record['corrective_action'],
                'operator': new_record['operator'],
                'comments': new_record['comments'],
                'sites': new_record['sites']
            }

            # Emit the new record via Socket.IO
            socketio.emit('new_density_record', new_record_dict)
            flash("Data inserted successfully.", "success")
            return redirect(url_for('density'))

        except ValueError as e:
            flash(f"Invalid numeric input: {e}", "danger")
            return redirect(url_for('density'))
        except Exception as e:
            logger.error(f"Error inserting density data: {e}", exc_info=True)
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for('density'))
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    else:
        site_filter = request.args.get('site')
        records = fetch_density_data(site_filter)
        unique_sites = sorted({record['sites'] for record in records if record['sites']})
        return render_template("density.html", records=records, unique_sites=unique_sites)

def fetch_deposition_data(filter_site=None):
    """Retrieves records from discharge_pipeline, optionally filtered by site."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = """
            SELECT id, date, time, discharge_location, discharge_coordinates,
                   flow_direction, water_distance_from_dike, compliance,
                   corrective_action, responsible, comments, sites
            FROM discharge_pipeline
        """
        params = []
        
        if filter_site:
            query += " WHERE sites = %s"
            params.append(filter_site)
            
        query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        records = []
        for row in rows:
            record = {
                'id': row[0],
                'date': row[1].strftime('%Y-%m-%d') if row[1] else '',
                'time': row[2].strftime('%H:%M:%S') if row[2] else '',
                'discharge_location': row[3],
                'discharge_coordinates': row[4],
                'flow_direction': row[5],
                'water_distance_from_dike': float(row[6]) if row[6] else None,
                'compliance': row[7],
                'corrective_action': row[8],
                'responsible': row[9],
                'comments': row[10],
                'sites': row[11]
            }
            records.append(record)
        return records
    except Exception as e:
        logger.error(f"Error fetching deposition data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_sites1():
    """Retrieves a list of distinct sites from the discharge_pipeline table."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = "SELECT DISTINCT sites FROM discharge_pipeline WHERE sites IS NOT NULL ORDER BY sites ASC;"
        cur.execute(query)
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching sites: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

@app.route('/deposition', methods=['GET', 'POST'])
@login_required
def deposition():
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['date', 'time', 'discharge_location', 'discharge_coordinates',
                             'flow_direction', 'water_distance_from_dike', 'responsible', 'site']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f"{field.replace('_', ' ').title()} is required", 'danger')
                    return redirect(url_for('deposition'))

            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            time_val = datetime.strptime(request.form['time'], '%H:%M').time()
            discharge_location = request.form['discharge_location']
            discharge_coordinates = request.form['discharge_coordinates']
            flow_direction = request.form['flow_direction']
            water_distance_from_dike = float(request.form['water_distance_from_dike'])
            if water_distance_from_dike < 0:
                raise ValueError("Water distance must be a non-negative number.")
            compliance = request.form.get('compliance') == 'on'
            corrective_action = request.form['corrective_action']
            responsible = request.form['responsible']
            comments = request.form.get('comments', '')
            sites = request.form['site']

            # Insert the new record
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed.")
                
            cur = conn.cursor()
            insert_query = """
                INSERT INTO discharge_pipeline 
                (date, time, discharge_location, discharge_coordinates, flow_direction,
                 water_distance_from_dike, compliance, corrective_action, responsible, comments, sites)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            cur.execute(insert_query, (
                date, time_val, discharge_location, discharge_coordinates, flow_direction,
                water_distance_from_dike, compliance, corrective_action, responsible, comments, sites
            ))
            conn.commit()
            
            flash("New record added successfully!", "success")
            return redirect(url_for('deposition'))
            
        except ValueError as e:
            flash(f"Invalid input: {e}", "error")
            return redirect(url_for('deposition'))
        except Exception as e:
            logger.error(f"Error inserting deposition data: {e}", exc_info=True)
            flash(f"An error occurred: {e}", "error")
            return redirect(url_for('deposition'))
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    else:
        site_filter = request.args.get('site')
        records = fetch_deposition_data(site_filter)
        sites = fetch_sites1()
        return render_template('deposition.html', records=records, sites=sites)

def fetch_leaks_data(site_filter=None):
    """Retrieves records from leaks_spills, optionally filtered by site."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        base_query = """
            SELECT id, date, time, pipeline_location, sites, incident_type, spilled_volume,
                   severity, probable_cause, corrective_action, status, operator, comments
            FROM leaks_spills
        """
        params = []
        
        if site_filter:
            base_query += " WHERE sites = %s"
            params.append(site_filter)
            
        base_query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
        
        records = []
        for row in rows:
            record = {
                'id': row[0],
                'date': row[1].strftime('%Y-%m-%d') if row[1] else '',
                'time': row[2].strftime('%H:%M:%S') if row[2] else '',
                'pipeline_location': row[3],
                'sites': row[4],
                'incident_type': row[5],
                'spilled_volume': float(row[6]) if row[6] else None,
                'severity': row[7],
                'probable_cause': row[8],
                'corrective_action': row[9],
                'status': row[10],
                'operator': row[11],
                'comments': row[12]
            }
            records.append(record)
        
        return records
    except Exception as e:
        logger.error(f"Error fetching leaks data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def get_site_options():
    """Fetch distinct sites from leaks_spills for the dropdown filter."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = "SELECT DISTINCT sites FROM leaks_spills WHERE sites IS NOT NULL ORDER BY sites ASC;"
        cur.execute(query)
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching leak sites: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

@app.route('/leaks', methods=['GET', 'POST'])
@login_required
def leaks():
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['date', 'time', 'pipeline_location', 'site', 'incident_type',
                             'spilled_volume', 'severity', 'probable_cause', 'status', 'operator']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f"{field.replace('_', ' ').title()} is required", 'danger')
                    return redirect(url_for('leaks'))

            date = request.form['date']
            time_val = request.form['time']
            pipeline_location = request.form['pipeline_location']
            site = request.form['site']
            incident_type = request.form['incident_type']
            spilled_volume = float(request.form['spilled_volume'])
            severity = request.form['severity']
            probable_cause = request.form['probable_cause']
            corrective_action = request.form['corrective_action']
            status = request.form['status']
            operator = request.form['operator']
            comments = request.form.get('comments', '')

            # Insert the new record
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed.")
                
            cur = conn.cursor()
            insert_query = """
                INSERT INTO leaks_spills 
                (date, time, pipeline_location, sites, incident_type, spilled_volume, 
                 severity, probable_cause, corrective_action, status, operator, comments)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            cur.execute(insert_query, (
                date, time_val, pipeline_location, site, incident_type, spilled_volume,
                severity, probable_cause, corrective_action, status, operator, comments
            ))
            conn.commit()
            
            flash("Record added successfully!", "success")
            return redirect(url_for('leaks'))
            
        except ValueError as e:
            flash(f"Invalid numeric input: {e}", "danger")
            return redirect(url_for('leaks'))
        except Exception as e:
            logger.error(f"Error inserting leak data: {e}", exc_info=True)
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for('leaks'))
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    else:
        site_filter = request.args.get('site')
        records = fetch_leaks_data(site_filter)
        sites = get_site_options()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(records)
        else:
            return render_template('leaks.html', records=records, sites=sites)

def fetch_sites():
    """Retrieves distinct, non-null site names from the condition_pipe_valve table."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT sites FROM condition_pipe_valve WHERE sites IS NOT NULL ORDER BY sites;")
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching pipe sites: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_pipes_data(site_filter=None):
    """Retrieves records from condition_pipe_valve, optionally filtered by site."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        select_query = """
            SELECT date, time, segment, visual_status, zone, problem_detected, measured_pressure,
                   compliance, corrective_action, operator, comments, sites
            FROM condition_pipe_valve
        """
        params = []
        
        if site_filter:
            select_query += " WHERE sites = %s"
            params.append(site_filter)
            
        select_query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(select_query, tuple(params))
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching pipes data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

@app.route('/pipes', methods=['GET', 'POST'])
@login_required
def pipes():
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['date', 'time', 'segment', 'sites', 'operator']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f"{field.replace('_', ' ').title()} is required", 'danger')
                    return redirect(url_for('pipes'))

            date_str = request.form['date']
            time_str = request.form['time']
            segment = request.form['segment']
            sites = request.form['sites']
            visual_status = request.form.get('visual_status', '')
            zone = request.form.get('zone', '')
            problem_detected = 'problem_detected' in request.form
            measured_pressure_str = request.form.get('measured_pressure', '')
            compliance = 'compliance' in request.form
            corrective_action = request.form.get('corrective_action', '')
            operator = request.form['operator']
            comments = request.form.get('comments', '')

            # Convert and validate data
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            measured_pressure = float(measured_pressure_str) if measured_pressure_str else None

            # Insert the record
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed.")
                
            cur = conn.cursor()
            insert_query = """
                INSERT INTO condition_pipe_valve
                (date, time, segment, visual_status, zone, problem_detected,
                 measured_pressure, compliance, corrective_action, operator, comments, sites)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
            """
            cur.execute(insert_query, (
                date_obj, time_obj, segment, visual_status, zone, problem_detected,
                measured_pressure, compliance, corrective_action, operator, comments, sites
            ))

            new_record = cur.fetchone()
            conn.commit()
            
            # Prepare the new record for Socket.IO emission
            new_record_dict = {
                'date': new_record[0].strftime('%Y-%m-%d') if new_record[0] else '',
                'time': new_record[1].strftime('%H:%M') if new_record[1] else '',
                'segment': new_record[2],
                'visual_status': new_record[3],
                'zone': new_record[4],
                'problem_detected': new_record[5],
                'measured_pressure': float(new_record[6]) if new_record[6] is not None else None,
                'compliance': new_record[7],
                'corrective_action': new_record[8],
                'operator': new_record[9],
                'comments': new_record[10],
                'sites': new_record[11]
            }

            socketio.emit('new_pipe_record', new_record_dict)
            flash("Record inserted successfully!", "success")
            return redirect(url_for('pipes'))
            
        except ValueError as e:
            flash(f"Invalid numeric input: {e}", "danger")
            return redirect(url_for('pipes'))
        except Exception as e:
            logger.error(f"Error inserting pipe data: {e}", exc_info=True)
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for('pipes'))
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    else:
        site_filter = request.args.get('site')
        records = fetch_pipes_data(site_filter)
        sites = fetch_sites()
        return render_template('pipes.html', records=records, sites=sites)

@app.route('/wall')
@login_required
def wall():
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed', 'danger')
        return render_template('wall.html', 
                           suintement_records=[],
                           tuyauterie_records=[],
                           erosion_records=[],
                           fissuration_records=[],
                           sites=[])
                           
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Retrieve records from each table
        cur.execute("SELECT * FROM preuve_suintement ORDER BY date DESC;")
        suintement_records = cur.fetchall()
        
        cur.execute("SELECT * FROM preuve_tuyauterie ORDER BY date DESC;")
        tuyauterie_records = cur.fetchall()
        
        cur.execute("SELECT * FROM preuve_erosion ORDER BY date DESC;")
        erosion_records = cur.fetchall()
        
        cur.execute("SELECT * FROM preuve_fissuration_glissement ORDER BY date DESC;")
        fissuration_records = cur.fetchall()
        
        # Get distinct sites from all four tables
        cur.execute("""
          SELECT DISTINCT site FROM (
            SELECT site FROM preuve_suintement
            UNION
            SELECT site FROM preuve_tuyauterie
            UNION
            SELECT site FROM preuve_erosion
            UNION
            SELECT site FROM preuve_fissuration_glissement
          ) AS all_sites WHERE site IS NOT NULL ORDER BY site;
        """)
        sites = [row['site'] for row in cur.fetchall()]
        
        return render_template('wall.html', 
                           suintement_records=suintement_records,
                           tuyauterie_records=tuyauterie_records,
                           erosion_records=erosion_records,
                           fissuration_records=fissuration_records,
                           sites=sites)
    except Exception as e:
        logger.error(f"Error fetching wall data: {e}")
        flash('An error occurred while fetching data', 'danger')
        return render_template('wall.html', 
                           suintement_records=[],
                           tuyauterie_records=[],
                           erosion_records=[],
                           fissuration_records=[],
                           sites=[])
    finally:
        cur.close()
        conn.close()

@app.route('/insert_suintement', methods=['POST'])
@login_required
def insert_suintement():
    try:
        # Validate required fields
        required_fields = ['suintement_date', 'suintement_heure', 'suintement_emplacement',
                         'suintement_site', 'suintement_surface', 'suintement_debit',
                         'suintement_couleur', 'suintement_gravite', 'suintement_responsable']
        for field in required_fields:
            if not request.form.get(field):
                flash(f"{field.replace('suintement_', '').replace('_', ' ').title()} is required", 'danger')
                return redirect(url_for('wall'))

        date = request.form['suintement_date']
        heure = request.form['suintement_heure']
        emplacement = request.form['suintement_emplacement']
        site = request.form['suintement_site']
        surface_affectee_m2 = float(request.form['suintement_surface'])
        debit_estime_lmin = float(request.form['suintement_debit'])
        couleur_eau = request.form['suintement_couleur']
        gravite = request.form['suintement_gravite']
        action_corrective = request.form.get('suintement_action', '')
        responsable = request.form['suintement_responsable']
        commentaires = request.form.get('suintement_commentaires', '')
        date_reparation = request.form.get('suintement_date_reparation', None)

        conn = get_db_connection()
        if not conn:
            raise Exception("Database connection failed.")
            
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO preuve_suintement
              (date, heure, emplacement, site, surface_affectee_m2, debit_estime_lmin, 
               couleur_eau, gravite, action_corrective, responsable, commentaires, date_reparation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (date, heure, emplacement, site, surface_affectee_m2, debit_estime_lmin, 
              couleur_eau, gravite, action_corrective, responsable, commentaires, date_reparation))
        conn.commit()
        
        socketio.emit('update_table', {'table': 'suintement'})
        flash("Record added successfully!", "success")
        return redirect(url_for('wall'))
        
    except ValueError as e:
        flash(f"Invalid numeric input: {e}", "danger")
        return redirect(url_for('wall'))
    except Exception as e:
        logger.error(f"Error inserting suintement data: {e}", exc_info=True)
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('wall'))
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/insert_tuyauterie', methods=['POST'])
@login_required
def insert_tuyauterie():
    try:
        # Validate required fields
        required_fields = ['tuyauterie_date', 'tuyauterie_heure', 'tuyauterie_emplacement',
                         'tuyauterie_site', 'tuyauterie_profondeur', 'tuyauterie_diametre',
                         'tuyauterie_gravite', 'tuyauterie_responsable']
        for field in required_fields:
            if not request.form.get(field):
                flash(f"{field.replace('tuyauterie_', '').replace('_', ' ').title()} is required", 'danger')
                return redirect(url_for('wall'))

        date = request.form['tuyauterie_date']
        heure = request.form['tuyauterie_heure']
        emplacement = request.form['tuyauterie_emplacement']
        site = request.form['tuyauterie_site']
        type_tuyauterie = request.form.get('tuyauterie_type', '')
        profondeur_estimee_cm = float(request.form['tuyauterie_profondeur'])
        diametre_mm = float(request.form['tuyauterie_diametre'])
        gravite = request.form['tuyauterie_gravite']
        action_corrective = request.form.get('tuyauterie_action', '')
        responsable = request.form['tuyauterie_responsable']
        commentaires = request.form.get('tuyauterie_commentaires', '')
        
        conn = get_db_connection()
        if not conn:
            raise Exception("Database connection failed.")
            
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO preuve_tuyauterie
              (date, heure, emplacement, site, type_tuyauterie, profondeur_estimee_cm, 
               diametre_mm, gravite, action_corrective, responsable, commentaires)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (date, heure, emplacement, site, type_tuyauterie, profondeur_estimee_cm, 
              diametre_mm, gravite, action_corrective, responsable, commentaires))
        conn.commit()
        
        socketio.emit('update_table', {'table': 'tuyauterie'})
        flash("Record added successfully!", "success")
        return redirect(url_for('wall'))
        
    except ValueError as e:
        flash(f"Invalid numeric input: {e}", "danger")
        return redirect(url_for('wall'))
    except Exception as e:
        logger.error(f"Error inserting tuyauterie data: {e}", exc_info=True)
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('wall'))
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
@app.route('/insert_erosion', methods=['POST'])
@login_required
def insert_erosion():
    try:
        # Validate required fields
        required_fields = ['erosion_date', 'erosion_heure', 'erosion_emplacement',
                         'erosion_site', 'erosion_zone', 'erosion_profondeur',
                         'erosion_gravite', 'erosion_responsable']
        for field in required_fields:
            if not request.form.get(field):
                flash(f"{field.replace('erosion_', '').replace('_', ' ').title()} is required", 'danger')
                return redirect(url_for('wall'))

        date = request.form['erosion_date']
        heure = request.form['erosion_heure']
        emplacement = request.form['erosion_emplacement']
        site = request.form['erosion_site']
        zone_erodee_m2 = float(request.form['erosion_zone'])
        profondeur_erosion_cm = float(request.form['erosion_profondeur'])
        type_erosion = request.form.get('erosion_type', '')
        gravite = request.form['erosion_gravite']
        action_corrective = request.form.get('erosion_action', '')
        responsable = request.form['erosion_responsable']
        commentaires = request.form.get('erosion_commentaires', '')
        statut = request.form.get('erosion_statut', '')
        date_reparation = request.form.get('erosion_date_reparation', None)
        
        conn = get_db_connection()
        if not conn:
            raise Exception("Database connection failed.")
            
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO preuve_erosion
              (date, heure, emplacement, site, zone_erodee_m2, profondeur_erosion_cm, 
               type_erosion, gravite, action_corrective, responsable, commentaires, 
               statut, date_reparation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (date, heure, emplacement, site, zone_erodee_m2, profondeur_erosion_cm, 
              type_erosion, gravite, action_corrective, responsable, commentaires,
              statut, date_reparation))
        conn.commit()
        
        socketio.emit('update_table', {'table': 'erosion'})
        flash("Record added successfully!", "success")
        return redirect(url_for('wall'))
        
    except ValueError as e:
        flash(f"Invalid numeric input: {e}", "danger")
        return redirect(url_for('wall'))
    except Exception as e:
        logger.error(f"Error inserting erosion data: {e}", exc_info=True)
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('wall'))
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/insert_fissuration', methods=['POST'])
@login_required
def insert_fissuration():
    try:
        # Validate required fields
        required_fields = ['fissuration_date', 'fissuration_heure', 'fissuration_emplacement',
                         'fissuration_site', 'fissuration_longueur', 'fissuration_largeur',
                         'fissuration_profondeur', 'fissuration_gravite', 'fissuration_responsable']
        for field in required_fields:
            if not request.form.get(field):
                flash(f"{field.replace('fissuration_', '').replace('_', ' ').title()} is required", 'danger')
                return redirect(url_for('wall'))

        date = request.form['fissuration_date']
        heure = request.form['fissuration_heure']
        emplacement = request.form['fissuration_emplacement']
        site = request.form['fissuration_site']
        type_fissure = request.form.get('fissuration_type_fissure', '')
        longueur_m = float(request.form['fissuration_longueur'])
        largeur_mm = float(request.form['fissuration_largeur'])
        profondeur_cm = float(request.form['fissuration_profondeur'])
        signes_glissement = request.form.get('fissuration_signes') == 'on'
        gravite = request.form['fissuration_gravite']
        action_corrective = request.form.get('fissuration_action', '')
        responsable = request.form['fissuration_responsable']
        commentaires = request.form.get('fissuration_commentaires', '')
        
        conn = get_db_connection()
        if not conn:
            raise Exception("Database connection failed.")
            
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO preuve_fissuration_glissement
              (date, heure, emplacement, site, type_fissure, longueur_m, largeur_mm, 
               profondeur_cm, signes_glissement, gravite, action_corrective, 
               responsable, commentaires)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (date, heure, emplacement, site, type_fissure, longueur_m, largeur_mm, 
              profondeur_cm, signes_glissement, gravite, action_corrective, 
              responsable, commentaires))
        conn.commit()
        
        socketio.emit('update_table', {'table': 'fissuration'})
        flash("Record added successfully!", "success")
        return redirect(url_for('wall'))
        
    except ValueError as e:
        flash(f"Invalid numeric input: {e}", "danger")
        return redirect(url_for('wall'))
    except Exception as e:
        logger.error(f"Error inserting fissuration data: {e}", exc_info=True)
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('wall'))
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def fetch_sites2():
    """Fetch unique site names from all three tables."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = """
          SELECT DISTINCT sites FROM precipitation_measures WHERE sites IS NOT NULL
          UNION
          SELECT DISTINCT sites FROM weather_conditions WHERE sites IS NOT NULL
          UNION
          SELECT DISTINCT sites FROM reservoir_status WHERE sites IS NOT NULL
          ORDER BY sites;
        """
        cur.execute(query)
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching water management sites: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_precipitation_data(site=None):
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        if site and site != "all":
            select_query = """
                SELECT date, time, precipitation_volume_mm, precipitation_duration_hours, precipitation_type,
                       impact_on_dike, corrective_action, responsible, comments, sites
                FROM precipitation_measures
                WHERE sites = %s
                ORDER BY date DESC, time DESC;
            """
            cur.execute(select_query, (site,))
        else:
            select_query = """
                SELECT date, time, precipitation_volume_mm, precipitation_duration_hours, precipitation_type,
                       impact_on_dike, corrective_action, responsible, comments, sites
                FROM precipitation_measures
                ORDER BY date DESC, time DESC;
            """
            cur.execute(select_query)
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching precipitation data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_weather_data(site=None):
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        if site and site != "all":
            select_query = """
                SELECT date, time, temperature_c, wind_speed_kmh, wind_direction, relative_humidity_percent,
                       potential_impact, severity, corrective_action, responsible, sites
                FROM weather_conditions
                WHERE sites = %s
                ORDER BY date DESC, time DESC;
            """
            cur.execute(select_query, (site,))
        else:
            select_query = """
                SELECT date, time, temperature_c, wind_speed_kmh, wind_direction, relative_humidity_percent,
                       potential_impact, severity, corrective_action, responsible, sites
                FROM weather_conditions
                ORDER BY date DESC, time DESC;
            """
            cur.execute(select_query)
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_reservoir_data(site=None):
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        if site and site != "all":
            select_query = """
                SELECT date, time, freeboard_m, current_volume_m3, max_volume_m3, fill_percentage,
                       estimated_time_to_fill_days, required_action, responsible, comments, sites
                FROM reservoir_status
                WHERE sites = %s
                ORDER BY date DESC, time DESC;
            """
            cur.execute(select_query, (site,))
        else:
            select_query = """
                SELECT date, time, freeboard_m, current_volume_m3, max_volume_m3, fill_percentage,
                       estimated_time_to_fill_days, required_action, responsible, comments, sites
                FROM reservoir_status
                ORDER BY date DESC, time DESC;
            """
            cur.execute(select_query)
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching reservoir data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

@app.route('/water_management', methods=['GET', 'POST'])
@login_required
def water_management():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        try:
            # Validate required fields
            required_fields = ['date', 'time', 'site']
            if form_type == 'precipitation':
                required_fields.extend(['precipitation_volume_mm', 'precipitation_duration_hours',
                                      'precipitation_type', 'impact_on_dike', 'responsible'])
            elif form_type == 'weather':
                required_fields.extend(['temperature_c', 'wind_speed_kmh', 'wind_direction',
                                      'relative_humidity_percent', 'potential_impact', 'responsible'])
            elif form_type == 'reservoir':
                required_fields.extend(['freeboard_m', 'current_volume_m3', 'max_volume_m3',
                                      'fill_percentage', 'estimated_time_to_fill_days', 'responsible'])
            
            for field in required_fields:
                if not request.form.get(field):
                    flash(f"{field.replace('_', ' ').title()} is required", 'danger')
                    return redirect(url_for('water_management'))

            date_str = request.form['date']
            time_str = request.form['time']
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            site = request.form['site']

            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed.")
                
            cur = conn.cursor()

            if form_type == 'precipitation':
                precipitation_volume_mm = float(request.form['precipitation_volume_mm'])
                precipitation_duration_hours = float(request.form['precipitation_duration_hours'])
                precipitation_type = request.form['precipitation_type']
                impact_on_dike = request.form['impact_on_dike']
                corrective_action = request.form.get('corrective_action', '')
                responsible = request.form['responsible']
                comments = request.form.get('comments', '')

                insert_query = """
                    INSERT INTO precipitation_measures
                    (date, time, precipitation_volume_mm, precipitation_duration_hours, precipitation_type,
                     impact_on_dike, corrective_action, responsible, comments, sites)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                """
                cur.execute(insert_query, (
                    date_obj, time_obj, precipitation_volume_mm, precipitation_duration_hours, precipitation_type,
                    impact_on_dike, corrective_action, responsible, comments, site
                ))

            elif form_type == 'weather':
                temperature_c = float(request.form['temperature_c'])
                wind_speed_kmh = float(request.form['wind_speed_kmh'])
                wind_direction = request.form['wind_direction']
                relative_humidity_percent = float(request.form['relative_humidity_percent'])
                potential_impact = request.form['potential_impact']
                severity = request.form.get('severity', 'medium')
                corrective_action = request.form.get('corrective_action', '')
                responsible = request.form['responsible']

                insert_query = """
                    INSERT INTO weather_conditions
                    (date, time, temperature_c, wind_speed_kmh, wind_direction, relative_humidity_percent,
                     potential_impact, severity, corrective_action, responsible, sites)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                """
                cur.execute(insert_query, (
                    date_obj, time_obj, temperature_c, wind_speed_kmh, wind_direction, relative_humidity_percent,
                    potential_impact, severity, corrective_action, responsible, site
                ))

            elif form_type == 'reservoir':
                freeboard_m = float(request.form['freeboard_m'])
                current_volume_m3 = float(request.form['current_volume_m3'])
                max_volume_m3 = float(request.form['max_volume_m3'])
                fill_percentage = float(request.form['fill_percentage'])
                estimated_time_to_fill_days = float(request.form['estimated_time_to_fill_days'])
                required_action = request.form.get('required_action', '')
                responsible = request.form['responsible']
                comments = request.form.get('comments', '')

                insert_query = """
                    INSERT INTO reservoir_status
                    (date, time, freeboard_m, current_volume_m3, max_volume_m3, fill_percentage,
                     estimated_time_to_fill_days, required_action, responsible, comments, sites)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                """
                cur.execute(insert_query, (
                    date_obj, time_obj, freeboard_m, current_volume_m3, max_volume_m3, fill_percentage,
                    estimated_time_to_fill_days, required_action, responsible, comments, site
                ))

            new_record = cur.fetchone()
            conn.commit()
            flash(f"{form_type.replace('_', ' ').title()} data saved successfully!", "success")
            return redirect(url_for('water_management'))
            
        except ValueError as e:
            flash(f"Invalid numeric input: {e}", "danger")
            return redirect(url_for('water_management'))
        except Exception as e:
            logger.error(f"Error inserting water management data: {e}", exc_info=True)
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for('water_management'))
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    else:
        site_filter = request.args.get('site', 'all')
        precipitation_data = fetch_precipitation_data(site_filter)
        weather_data = fetch_weather_data(site_filter)
        reservoir_data = fetch_reservoir_data(site_filter)
        sites = fetch_sites2()

        return render_template('water_management.html',
                               precipitation_data=precipitation_data,
                               weather_data=weather_data,
                               reservoir_data=reservoir_data,
                               selected_site=site_filter,
                               sites=sites)

def fetch_discharge_fluid_clarity_data(site_filter=None):
    """Fetch records from Discharge_Fluid_Clarity, optionally filtered by site."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = """
            SELECT date, time, location, fluid_clarity, turbidity, observed_color, flow_rate,
                   corrective_action, responsible_person, comments, sites
            FROM Discharge_Fluid_Clarity
        """
        params = []
        
        if site_filter:
            query += " WHERE sites = %s"
            params.append(site_filter)
            
        query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        records = []
        for row in rows:
            record = {
                'date': row[0].strftime('%Y-%m-%d') if row[0] else '',
                'time': row[1].strftime('%H:%M:%S') if row[1] else '',
                'location': row[2],
                'fluid_clarity': row[3],
                'turbidity': int(row[4]) if row[4] else None,
                'observed_color': row[5],
                'flow_rate': float(row[6]) if row[6] else None,
                'corrective_action': row[7],
                'responsible_person': row[8],
                'comments': row[9],
                'sites': row[10]
            }
            records.append(record)
        return records
    except Exception as e:
        logger.error(f"Error fetching discharge fluid clarity data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_leak_signs_data(site_filter=None):
    """Fetch records from Leak_Signs, optionally filtered by site."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = """
            SELECT date, time, leak_location, estimated_flow_rate, exact_location, corrective_action,
                   repair_date, responsible_person, comments, sites
            FROM Leak_Signs
        """
        params = []
        
        if site_filter:
            query += " WHERE sites = %s"
            params.append(site_filter)
            
        query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        records = []
        for row in rows:
            record = {
                'date': row[0].strftime('%Y-%m-%d') if row[0] else '',
                'time': row[1].strftime('%H:%M:%S') if row[1] else '',
                'leak_location': row[2],
                'estimated_flow_rate': float(row[3]) if row[3] else None,
                'exact_location': row[4],
                'corrective_action': row[5],
                'repair_date': row[6].strftime('%Y-%m-%d') if row[6] else '',
                'responsible_person': row[7],
                'comments': row[8],
                'sites': row[9]
            }
            records.append(record)
        return records
    except Exception as e:
        logger.error(f"Error fetching leak signs data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_structural_integrity_data(site_filter=None):
    """Fetch records from Structural_Integrity_Water_Recovery, optionally filtered by site."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = """
            SELECT date, time, location, structure_condition, signs_of_corrosion, observed_deformation,
                   current_performance, corrective_action, responsible_person, comments, sites
            FROM Structural_Integrity_Water_Recovery
        """
        params = []
        
        if site_filter:
            query += " WHERE sites = %s"
            params.append(site_filter)
            
        query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        records = []
        for row in rows:
            record = {
                'date': row[0].strftime('%Y-%m-%d') if row[0] else '',
                'time': row[1].strftime('%H:%M:%S') if row[1] else '',
                'location': row[2],
                'structure_condition': row[3],
                'signs_of_corrosion': row[4],
                'observed_deformation': row[5],
                'current_performance': float(row[6]) if row[6] else None,
                'corrective_action': row[7],
                'responsible_person': row[8],
                'comments': row[9],
                'sites': row[10]
            }
            records.append(record)
        return records
    except Exception as e:
        logger.error(f"Error fetching structural integrity data: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

def fetch_water_recovery_sites():
    """Fetch unique site names from all three water recovery tables."""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        query = """
          SELECT DISTINCT sites FROM Discharge_Fluid_Clarity WHERE sites IS NOT NULL
          UNION
          SELECT DISTINCT sites FROM Leak_Signs WHERE sites IS NOT NULL
          UNION
          SELECT DISTINCT sites FROM Structural_Integrity_Water_Recovery WHERE sites IS NOT NULL
          ORDER BY sites;
        """
        cur.execute(query)
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching water recovery sites: {e}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()

@app.route('/water_recovery', methods=['GET', 'POST'])
@login_required
def water_recovery():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        try:
            # Validate required fields
            required_fields = ['date', 'time', 'site']
            if form_type == 'discharge_fluid_clarity':
                required_fields.extend(['location', 'fluid_clarity', 'turbidity', 
                                      'observed_color', 'flow_rate', 'responsible_person'])
            elif form_type == 'leak_signs':
                required_fields.extend(['leak_location', 'estimated_flow_rate', 
                                      'exact_location', 'responsible_person'])
            elif form_type == 'structural_integrity':
                required_fields.extend(['location', 'structure_condition', 
                                      'signs_of_corrosion', 'responsible_person'])
            
            for field in required_fields:
                if not request.form.get(field):
                    flash(f"{field.replace('_', ' ').title()} is required", 'danger')
                    return redirect(url_for('water_recovery'))

            date_str = request.form['date']
            time_str = request.form['time']
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            site = request.form['site']

            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed.")
                
            cur = conn.cursor()

            if form_type == 'discharge_fluid_clarity':
                location = request.form['location']
                fluid_clarity = request.form['fluid_clarity']
                turbidity = int(request.form['turbidity'])
                observed_color = request.form['observed_color']
                flow_rate = float(request.form['flow_rate'])
                corrective_action = request.form.get('corrective_action', '')
                responsible_person = request.form['responsible_person']
                comments = request.form.get('comments', '')

                insert_query = """
                    INSERT INTO Discharge_Fluid_Clarity
                    (date, time, location, fluid_clarity, turbidity, observed_color, flow_rate,
                     corrective_action, responsible_person, comments, sites)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                """
                cur.execute(insert_query, (
                    date_obj, time_obj, location, fluid_clarity, turbidity, observed_color,
                    flow_rate, corrective_action, responsible_person, comments, site
                ))

            elif form_type == 'leak_signs':
                leak_location = request.form['leak_location']
                estimated_flow_rate = float(request.form['estimated_flow_rate'])
                exact_location = request.form['exact_location']
                corrective_action = request.form.get('corrective_action', '')
                repair_date = request.form.get('repair_date', None)
                responsible_person = request.form['responsible_person']
                comments = request.form.get('comments', '')

                insert_query = """
                    INSERT INTO Leak_Signs
                    (date, time, leak_location, estimated_flow_rate, exact_location, corrective_action,
                     repair_date, responsible_person, comments, sites)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                """
                cur.execute(insert_query, (
                    date_obj, time_obj, leak_location, estimated_flow_rate, exact_location, corrective_action,
                    repair_date, responsible_person, comments, site
                ))

            elif form_type == 'structural_integrity':
                location = request.form['location']
                structure_condition = request.form['structure_condition']
                signs_of_corrosion = request.form['signs_of_corrosion']
                observed_deformation = request.form['observed_deformation']
                current_performance = float(request.form.get('current_performance', 0))
                corrective_action = request.form.get('corrective_action', '')
                responsible_person = request.form['responsible_person']
                comments = request.form.get('comments', '')

                insert_query = """
                    INSERT INTO Structural_Integrity_Water_Recovery
                    (date, time, location, structure_condition, signs_of_corrosion, observed_deformation,
                     current_performance, corrective_action, responsible_person, comments, sites)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                """
                cur.execute(insert_query, (
                    date_obj, time_obj, location, structure_condition, signs_of_corrosion, observed_deformation,
                    current_performance, corrective_action, responsible_person, comments, site
                ))

            new_record = cur.fetchone()
            conn.commit()
            flash(f"{form_type.replace('_', ' ').title()} data saved successfully!", "success")
            return redirect(url_for('water_recovery'))
            
        except ValueError as e:
            flash(f"Invalid numeric input: {e}", "danger")
            return redirect(url_for('water_recovery'))
        except Exception as e:
            logger.error(f"Error inserting water recovery data: {e}", exc_info=True)
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for('water_recovery'))
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    else:
        site_filter = request.args.get('site')
        discharge_fluid_clarity_data = fetch_discharge_fluid_clarity_data(site_filter)
        leak_signs_data = fetch_leak_signs_data(site_filter)
        structural_integrity_data = fetch_structural_integrity_data(site_filter)
        sites = fetch_water_recovery_sites()

        return render_template('water_recovery.html',
                               discharge_fluid_clarity_data=discharge_fluid_clarity_data,
                               leak_signs_data=leak_signs_data,
                               structural_integrity_data=structural_integrity_data,
                               sites=sites)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

if __name__ == '__main__':
    socketio.run(
    app,
    host='0.0.0.0',
    port=int(os.environ.get('PORT', 5000)),
    debug=os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't'),
    allow_unsafe_werkzeug=True
)
