# Core Flask
from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages, jsonify,session
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
from datetime import datetime

# Debugging
import traceback
import logging

# CORS
from flask_cors import CORS
# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
socketio = SocketIO(app)
CORS(app)

app.secret_key = os.getenv('SECRET_KEY', 'RRUETE56D')

# Define db_config (for your system's use)
db_config = {
    'dbname': 'railway',
    'user': 'postgres',
    'password': 'rrmqEaDpPExUAWstQdCUsxctBrrUYhTd',
    'host': 'metro.proxy.rlwy.net',
    'port': '15070'
}

# Build connection string from db_config
default_db_uri = (
    f"postgresql://{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
)

# Use DATABASE_URL environment variable if set, else fallback to built connection string
db_uri = os.getenv('DATABASE_URL', default_db_uri)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@app.route('/test_db')
def test_db():
    try:
        db.session.execute('SELECT 1')
        return "✅ Database connection successful"
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return f"❌ Connection failed: {e}"

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None

def fetch_dam_data():
    """Fetch dam data from the database and return as JSON."""
    conn = get_db_connection()
    if conn:
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
                    total_capex  -- Include total_capex from the database
                FROM managem_dams;
            """
            df = pd.read_sql(query, conn)
            conn.close()

            # Replace NaN values with None (which becomes null in JSON)
            df = df.where(pd.notnull(df), None)

            # Convert date fields to string if necessary
            date_fields = ['commission_date', 'complete_full_date', 'stop_definitive_date', 'date_of_actualisation']
            for field in date_fields:
                if field in df.columns:
                    df[field] = df[field].astype(str)

            # Convert data to JSON format
            data = df.to_dict(orient='records')
            return data
        except Exception as e:
            print(f"Error fetching data: {e}")
            return {'error': 'Failed to fetch data from the database.'}
    else:
        return {'error': 'Database connection failed.'}

@app.route('/')
def home():
    return redirect(url_for('login'))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
                
            if check_password_hash(user[2], password):  # password
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
                    app.logger.error(f"Failed to update last login: {e}")
                
                flash(f'Welcome back, {user[1]}!', 'success')
                # Redirect to index.html after successful login
                return redirect(url_for('index'))  # Changed from 'home' to 'index'
            else:
                flash('Invalid email or password', 'danger')
        except Exception as e:
            if conn:
                conn.rollback()
            flash('An error occurred during login', 'danger')
            app.logger.error(f"Login error: {e}", exc_info=True)
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    return render_template('login.html')

# Add this new route for index.html
@app.route('/index')
@login_required
def index():
    return render_template('index.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', '')
        
        # Validation based on your database schema
        errors = []
        
        # Username validation (text in schema)
        if len(username) < 3:
            errors.append('Username must be at least 3 characters')
        elif len(username) > 50:
            errors.append('Username must be less than 50 characters')
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers and underscores')
            
        # Email validation (text in schema)
        if not email:
            errors.append('Email is required')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Invalid email address')
        elif len(email) > 255:
            errors.append('Email must be less than 255 characters')
            
        # Password validation (text in schema)
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
            
        # Role validation (text in schema)
        valid_roles = ['geotechnical_engineer', 'tailing_system_engineer', 'hydrological_engineer']
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
            # Check for existing user (matches your schema fields)
            cur.execute(
                sql.SQL("""
                    SELECT id 
                    FROM users 
                    WHERE email = %s OR username = %s
                """),
                [email, username]
            )
            if cur.fetchone():
                flash('Email or username already exists', 'danger')
                return render_template('register.html',
                                    username=username,
                                    email=email,
                                    role=role)
                
            # Hash password (will be stored in password text field)
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            
            # Insert new user (matches your exact schema)
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
                    True,  # is_active as per your schema
                    datetime.now()  # created_at as per your schema
                ]
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            flash('Registration failed. Please try again.', 'danger')
            app.logger.error(f"Registration error for {email}: {e}", exc_info=True)
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
def index():
    """Render the main index page."""
    return render_template('index.html')

@app.route('/dams')
def dams():
    """Render the dams page."""
    return render_template('dams.html')

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    """Send the initial data when a client connects."""
    data = fetch_dam_data()
    socketio.emit('update_data', data)

@app.route('/daily', methods=['GET', 'POST'])
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
                'total_autonomy' # Replaced 'stockage_ratio' with 'total_autonomy'
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
            if conn is None:
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
            columns = [desc[0] for desc in cur.description] if last_entry else []

            # Collect optional fields
            for field in optional_fields:
                value = request.form.get(field)
                if value in (None, ''):
                    if last_entry and field in columns:
                        # Use the previous value
                        value = last_entry[columns.index(field)]
                    else:
                        # No previous value, set to None
                        value = None
                else:
                    # Convert to appropriate type
                    if field in ['commission_date', 'complete_full_date', 'stop_definitive_date']:
                        value = value  # Dates are kept as strings (assuming 'YYYY-MM-DD' format)
                    elif 'capex' in field or field == 'total_autonomy':  # Replaced 'stockage_ratio' with 'total_autonomy'
                        value = float(value)
                    else:
                        value = value  # Keep string values as is

                data[field] = value

            # Build the INSERT query dynamically based on the provided data
            insert_columns = data.keys()
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
            cur.close()
            conn.close()

            # Emit updated data to all connected clients
            socketio.emit('update_data', fetch_dam_data())

            # Redirect to the same page or render a success message
            return redirect(url_for('daily'))

        except Exception as e:
            print(f"Error inserting data: {e}")
            return render_template('daily.html', error=f"An error occurred: {e}")

    # For GET request, simply render the form
    return render_template('daily.html')


@app.route('/get_previous_data/<site>')
def get_previous_data(site):
    """Fetch the most recent data for the specified site."""
    conn = get_db_connection()
    if conn:
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
                    total_autonomy -- Replaced 'stockage_ratio' with 'total_autonomy'
                FROM managem_dams
                WHERE sites = %s
                ORDER BY date_of_actualisation DESC
                LIMIT 1
            ''', (site,))
            row = cur.fetchone()
            if row:
                # Map the fetched data to a dictionary
                columns = [desc[0] for desc in cur.description]
                data = dict(zip(columns, row))
                # Convert date fields to string if necessary
                date_fields = ['commission_date', 'complete_full_date', 'stop_definitive_date']
                for field in date_fields:
                    if data.get(field):
                        data[field] = data[field].strftime('%Y-%m-%d')
                return jsonify(data)
            else:
                return jsonify({})
        except Exception as e:
            print(f"Error fetching previous data: {e}")
            return jsonify({})
        finally:
            cur.close()
            conn.close()
    else:
        return jsonify({})
    



# Other routes as needed
@app.route('/geotechnical')
def geotechnical():
    return render_template('geotechnical.html')

@app.route('/weekly')
def weekly():
    return render_template('weekly.html')

@app.route('/monthly', methods=['GET', 'POST'])
def monthly():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Process form submissions
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            # Create a new record
            annee = request.form['annee']
            precipitation = request.form['precipitation_mm']
            if not annee or not precipitation:
                flash('Both Year and Precipitation are required!')
            else:
                try:
                    cur.execute(
                        'INSERT INTO climate_data (annee, precipitation_mm) VALUES (%s, %s)',
                        (annee, precipitation)
                    )
                    conn.commit()
                    flash('Record created successfully!')
                except Exception as e:
                    conn.rollback()
                    flash('Error creating record: ' + str(e))
        
        elif action == 'edit':
            # Update an existing record
            annee = request.form['annee']
            precipitation = request.form['precipitation_mm']
            if not precipitation:
                flash('Precipitation is required!')
            else:
                try:
                    cur.execute(
                        'UPDATE climate_data SET precipitation_mm = %s WHERE annee = %s',
                        (precipitation, annee)
                    )
                    conn.commit()
                    flash('Record updated successfully!')
                except Exception as e:
                    conn.rollback()
                    flash('Error updating record: ' + str(e))
        
        elif action == 'delete':
            # Delete a record
            annee = request.form['annee']
            try:
                cur.execute('DELETE FROM climate_data WHERE annee=%s', (annee,))
                conn.commit()
                flash('Record deleted successfully!')
            except Exception as e:
                conn.rollback()
                flash('Error deleting record: ' + str(e))
    
    # Fetch all records for display and charting
    cur.execute("SELECT * FROM climate_data ORDER BY annee")
    records = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('monthly.html', records=records)

@app.route('/yearly')
def yearly():
    return render_template('yearly.html')


@app.route('/environmental')
def environmental():
    return render_template('environmental.html')

@app.route('/rmr')
def rmr():
    return render_template('rmr.html')

def fetch_density_data():
    """Fetch all records from the density_controle table."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT date, time, zone_tailing_system, measured_density, targeted_density,
                   difference, corrective_action, operator, comments, sites
            FROM density_controle
            ORDER BY date, time;
        """)
        records = cur.fetchall()
        cur.close()
        conn.close()
        return records
    except Exception as e:
        logging.error("Error fetching data: %s", e)
        return []

# Route for the density page
@app.route('/density', methods=['GET', 'POST'])
def density():
    if request.method == 'POST':
        try:
            # Debugging: Print form data
            print("Form Data Received:", request.form)

            # Retrieve and validate form data
            date = request.form['date']
            time_val = request.form['time']
            zone_tailing_system = request.form['zone_tailing_system']
            measured_density = float(request.form['measured_density'])
            targeted_density = float(request.form['targeted_density'])
            corrective_action = request.form.get('corrective_action', '')
            operator = request.form['operator']
            comments = request.form.get('comments', '')
            sites = request.form['sites']

            # Debugging: Print parsed data
            print(f"Parsed Data: Date={date}, Time={time_val}, Zone={zone_tailing_system}, Measured={measured_density}, Targeted={targeted_density}, Operator={operator}, Sites={sites}")

            # Connect to the database
            conn = get_db_connection()
            if conn is None:
                raise Exception("Database connection failed.")
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # Insert the record (excluding the difference field)
            insert_query = """
                INSERT INTO density_controle 
                (date, time, zone_tailing_system, measured_density, targeted_density,
                 corrective_action, operator, comments, sites)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING date, time, zone_tailing_system, measured_density, targeted_density, difference,
                          corrective_action, operator, comments, sites;
            """
            cur.execute(insert_query, (
                date, time_val, zone_tailing_system, measured_density, targeted_density,
                corrective_action, operator, comments, sites
            ))

            # Commit the transaction
            new_record = cur.fetchone()
            conn.commit()
            logging.info("Record successfully committed: %s", new_record)

            # Format the new record for the response
            new_record_dict = {
                'date': new_record['date'].strftime('%Y-%m-%d') if new_record['date'] else '',
                'time': new_record['time'].strftime('%H:%M:%S') if new_record['time'] else '',
                'zone_tailing_system': new_record['zone_tailing_system'],
                'measured_density': new_record['measured_density'],
                'targeted_density': new_record['targeted_density'],
                'difference': new_record['difference'],  # This will be calculated by the database
                'corrective_action': new_record['corrective_action'],
                'operator': new_record['operator'],
                'comments': new_record['comments'],
                'sites': new_record['sites']
            }

            # Emit the new record via Socket.IO
            socketio.emit('new_record', new_record_dict, broadcast=True)
            flash("Data inserted successfully.", "success")
            return redirect(url_for('density'))

        except psycopg2.Error as e:
            logging.error("Database error: %s", e)
            flash("Database error: " + str(e), "danger")
            return redirect(url_for('density'))
        except Exception as e:
            logging.error("Error inserting data: %s", e)
            flash("An error occurred while inserting data: " + str(e), "danger")
            return redirect(url_for('density'))
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    else:
        records = fetch_density_data()
        unique_sites = sorted(set(record['sites'] for record in records if record['sites']))
        return render_template("density.html", records=records, unique_sites=unique_sites)
def fetch_deposition_data(filter_site=None):
    """
    Retrieves all records from discharge_pipeline.
    If filter_site is provided, only records from that site are returned.
    """
    conn = get_db_connection()
    if conn is None:
        raise Exception("Database connection failed.")
    
    try:
        cur = conn.cursor()
        query = """
            SELECT id, date, time, discharge_location, discharge_coordinates,
                   flow_direction, water_distance_from_dike, compliance,
                   corrective_action, responsible, comments, sites
            FROM discharge_pipeline
        """
        if filter_site:
            query += " WHERE sites = %s"
            params = (filter_site,)
        else:
            params = ()
        
        query += " ORDER BY date DESC, time DESC;"
        
        cur.execute(query, params)
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
                'water_distance_from_dike': row[6],
                'compliance': row[7],
                'corrective_action': row[8],
                'responsible': row[9],
                'comments': row[10],
                'sites': row[11]
            }
            records.append(record)
        return records
    finally:
        cur.close()
        conn.close()

def fetch_sites1():
    """
    Retrieves a list of distinct sites from the discharge_pipeline table.
    """
    conn = get_db_connection()
    if conn is None:
        raise Exception("Database connection failed.")
    
    try:
        cur = conn.cursor()
        query = "SELECT DISTINCT sites FROM discharge_pipeline ORDER BY sites ASC;"
        cur.execute(query)
        rows = cur.fetchall()
        sites = [row[0] for row in rows if row[0]]
        return sites
    finally:
        cur.close()
        conn.close()

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.route('/deposition', methods=['GET', 'POST'])
def deposition():
    if request.method == 'POST':
        try:
            logger.debug("Form Data: %s", request.form)  # Log the form data
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
            sites = request.form['site']  # Form field is named 'site'

            # Insert the new record into the database
            conn = get_db_connection()
            if conn is None:
                raise Exception("Database connection failed.")
            
            try:
                cur = conn.cursor()
                insert_query = """
                    INSERT INTO discharge_pipeline 
                    (date, time, discharge_location, discharge_coordinates, flow_direction,
                     water_distance_from_dike, compliance, corrective_action, responsible, comments, sites)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, date, time, discharge_location, discharge_coordinates,
                              flow_direction, water_distance_from_dike, compliance,
                              corrective_action, responsible, comments, sites;
                """
                cur.execute(insert_query, (
                    date, time_val, discharge_location, discharge_coordinates, flow_direction,
                    water_distance_from_dike, compliance, corrective_action, responsible, comments, sites
                ))
                new_record = cur.fetchone()
                conn.commit()
                flash("New record added successfully!", "success")
                return redirect(url_for('deposition'))
            finally:
                cur.close()
                conn.close()
        except ValueError as e:
            logger.error("Invalid input: %s", e, exc_info=True)
            flash(f"Invalid input: {e}", "error")
            return redirect(url_for('deposition'))
        except Exception as e:
            logger.error("Error inserting data: %s", e, exc_info=True)
            flash(f"An error occurred while inserting data: {e}", "error")
            return redirect(url_for('deposition'))
    else:
        # Retrieve filter parameter (if any) and fetch matching records
        site_filter = request.args.get('site')
        records = fetch_deposition_data(site_filter)
        sites = fetch_sites1()
        return render_template('deposition.html', records=records, sites=sites)
def fetch_leaks_data(site_filter=None):
    """
    Retrieves all records from the leaks_spills table and returns a list of dictionaries.
    Expected columns (in order):
      id, date, time, pipeline_location, sites, incident_type, spilled_volume,
      severity, probable_cause, corrective_action, status, operator, comments
    """
    conn = get_db_connection()
    if conn is None:
        raise Exception("Database connection failed.")
    
    cur = conn.cursor()
    base_query = """
        SELECT id, date, time, pipeline_location, sites, incident_type, spilled_volume,
               severity, probable_cause, corrective_action, status, operator, comments
        FROM leaks_spills
    """
    params = []
    if site_filter:
        base_query += " WHERE sites = %s "
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
            'spilled_volume': row[6],
            'severity': row[7],
            'probable_cause': row[8],
            'corrective_action': row[9],
            'status': row[10],
            'operator': row[11],
            'comments': row[12]
        }
        records.append(record)
    
    cur.close()
    conn.close()
    return records

def get_site_options():
    """Fetch distinct sites from leaks_spills for the dropdown filter."""
    conn = get_db_connection()
    if conn is None:
        raise Exception("Database connection failed.")
    cur = conn.cursor()
    query = "SELECT DISTINCT sites FROM leaks_spills ORDER BY sites ASC;"
    cur.execute(query)
    sites = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return sites

@app.route('/leaks', methods=['GET', 'POST'])
def leaks():
    if request.method == 'POST':
        try:
            # Retrieve form data from request.
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

            # Insert the new record into the database.
            conn = get_db_connection()
            if conn is None:
                raise Exception("Database connection failed.")
            cur = conn.cursor()
            insert_query = """
                INSERT INTO leaks_spills 
                (date, time, pipeline_location, sites, incident_type, spilled_volume, severity, probable_cause, corrective_action, status, operator, comments)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, date, time, pipeline_location, sites, incident_type, spilled_volume, severity, probable_cause, corrective_action, status, operator, comments;
            """
            cur.execute(insert_query, (
                date, time_val, pipeline_location, site, incident_type, spilled_volume, severity,
                probable_cause, corrective_action, status, operator, comments
            ))
            new_record = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()

            new_record_dict = {
                'id': new_record[0],
                'date': new_record[1].strftime('%Y-%m-%d') if new_record[1] else '',
                'time': new_record[2].strftime('%H:%M:%S') if new_record[2] else '',
                'pipeline_location': new_record[3],
                'sites': new_record[4],
                'incident_type': new_record[5],
                'spilled_volume': new_record[6],
                'severity': new_record[7],
                'probable_cause': new_record[8],
                'corrective_action': new_record[9],
                'status': new_record[10],
                'operator': new_record[11],
                'comments': new_record[12]
            }

            # Emit the new record via SocketIO so that any connected clients can update.
            socketio.emit('new_record', new_record_dict, broadcast=True)
            return jsonify(new_record_dict)
        except Exception as e:
            print(f"Error inserting data: {e}")
            flash(f"An error occurred while inserting data: {e}")
            # For AJAX requests, a JSON response may be preferable.
            return jsonify({'error': str(e)}), 500
    else:
        site_filter = request.args.get('site')
        records = fetch_leaks_data(site_filter)
        sites = get_site_options()
        # If this is an AJAX request, return JSON.
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(records)
        else:
            return render_template('leaks.html', records=records, sites=sites)
# Returns a list of distinct sites from the database.
def fetch_sites():
    """
    Retrieves distinct, non-null site names from the condition_pipe_valve table.
    """
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database")
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT sites FROM condition_pipe_valve ORDER BY sites;")
        sites = cur.fetchall()
        cur.close()
        conn.close()
        return [s[0] for s in sites if s[0]]
    except Exception as e:
        print(f"Error fetching sites: {e}")
        if conn:
            conn.close()
        return []

def fetch_pipes_data():
    """
    Retrieves all records from the condition_pipe_valve table ordered by date and time descending.
    """
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return []
    try:
        cur = conn.cursor()
        select_query = """
            SELECT date, time, segment, visual_status, zone, problem_detected, measured_pressure,
                   compliance, corrective_action, operator, comments, sites
            FROM condition_pipe_valve
            ORDER BY date DESC, time DESC;
        """
        cur.execute(select_query)
        records = cur.fetchall()
        print(f"Fetched records: {records}")  # Debug statement
        cur.close()
        conn.close()
        return records
    except Exception as e:
        print(f"Error fetching data: {e}")
        if conn:
            conn.close()
        flash(f"An error occurred while fetching data: {e}")
        return []

@app.route('/pipes', methods=['GET', 'POST'])
def pipes():
    if request.method == 'POST':
        try:
            # Retrieve form data. (Ensure your HTML form uses the field name "sites".)
            date_str = request.form['date']
            time_str = request.form['time']
            segment = request.form['segment']
            sites = request.form['sites']  # Must match the backend column and HTML field name
            visual_status = request.form.get('visual_status', '')
            zone = request.form.get('zone', '')
            problem_detected = 'problem_detected' in request.form
            measured_pressure_str = request.form.get('measured_pressure', None)
            compliance = 'compliance' in request.form
            corrective_action = request.form.get('corrective_action', '')
            operator = request.form['operator']
            comments = request.form.get('comments', '')

            # Debug: Print received form data.
            print("Received form data:")
            print(f"  Date: {date_str}")
            print(f"  Time: {time_str}")
            print(f"  Segment: {segment}")
            print(f"  Sites: {sites}")
            print(f"  Visual Status: {visual_status}")
            print(f"  Zone: {zone}")
            print(f"  Problem Detected: {problem_detected}")
            print(f"  Measured Pressure: {measured_pressure_str}")
            print(f"  Compliance: {compliance}")
            print(f"  Corrective Action: {corrective_action}")
            print(f"  Operator: {operator}")
            print(f"  Comments: {comments}")

            # Convert date and time strings to Python objects.
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            measured_pressure = float(measured_pressure_str) if measured_pressure_str else None

            # Open a database connection.
            conn = get_db_connection()
            if conn is None:
                raise Exception("Database connection failed.")
            cur = conn.cursor()

            # Use the RETURNING clause (works with PostgreSQL) to get the inserted row.
            insert_query = """
                INSERT INTO condition_pipe_valve
                (date, time, segment, visual_status, zone, problem_detected,
                 measured_pressure, compliance, corrective_action, operator, comments, sites)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING date, time, segment, visual_status, zone, problem_detected,
                          measured_pressure, compliance, corrective_action, operator, comments, sites;
            """
            cur.execute(insert_query, (
                date_obj, time_obj, segment, visual_status, zone, problem_detected,
                measured_pressure, compliance, corrective_action, operator, comments, sites
            ))

            new_record = cur.fetchone()
            conn.commit()
            print("Rows affected:", cur.rowcount)
            cur.close()
            conn.close()

            # Prepare the new record for Socket.IO emission.
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

            socketio.emit('new_record', new_record_dict, broadcast=True)
            print("Record inserted and emitted:", new_record_dict)

            # Redirect to avoid multiple form submissions.
            return redirect(url_for('pipes'))
        except Exception as e:
            traceback.print_exc()
            flash(f"An error occurred while inserting data: {e}")
            return redirect(url_for('pipes'))
    else:
        records = fetch_pipes_data()
        sites = fetch_sites()
        print(f"Records passed to template: {records}")
        return render_template('pipes.html', records=records, sites=sites)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
@app.route('/wall')
def wall():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Retrieve records from each table.
    cur.execute("SELECT * FROM preuve_suintement ORDER BY date DESC;")
    suintement_records = cur.fetchall()
    
    cur.execute("SELECT * FROM preuve_tuyauterie ORDER BY date DESC;")
    tuyauterie_records = cur.fetchall()
    
    cur.execute("SELECT * FROM preuve_erosion ORDER BY date DESC;")
    erosion_records = cur.fetchall()
    
    cur.execute("SELECT * FROM preuve_fissuration_glissement ORDER BY date DESC;")
    fissuration_records = cur.fetchall()
    
    # Get distinct sites from all four tables.
    cur.execute("""
      SELECT DISTINCT site FROM (
        SELECT site FROM preuve_suintement
        UNION
        SELECT site FROM preuve_tuyauterie
        UNION
        SELECT site FROM preuve_erosion
        UNION
        SELECT site FROM preuve_fissuration_glissement
      ) AS all_sites ORDER BY site;
    """)
    sites = cur.fetchall()
    cur.close()
    conn.close()
    
    # Convert the results to a simple list of site strings.
    site_list = [row['site'] for row in sites]
    
    return render_template('wall.html', 
                           suintement_records=suintement_records,
                           tuyauterie_records=tuyauterie_records,
                           erosion_records=erosion_records,
                           fissuration_records=fissuration_records,
                           sites=site_list)

# -------------------------
# INSERT ROUTES FOR EACH TABLE
# -------------------------

@app.route('/insert_suintement', methods=['POST'])
def insert_suintement():
    date = request.form.get('suintement_date')
    heure = request.form.get('suintement_heure')
    emplacement = request.form.get('suintement_emplacement')
    site = request.form.get('suintement_site')
    surface_affectee_m2 = request.form.get('suintement_surface')
    debit_estime_lmin = request.form.get('suintement_debit')
    couleur_eau = request.form.get('suintement_couleur')
    gravite = request.form.get('suintement_gravite')
    action_corrective = request.form.get('suintement_action')
    responsable = request.form.get('suintement_responsable')
    commentaires = request.form.get('suintement_commentaires')
    date_reparation = request.form.get('suintement_date_reparation')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO preuve_suintement
          (date, heure, emplacement, site, surface_affectee_m2, debit_estime_lmin, couleur_eau, gravite, action_corrective, responsable, commentaires, date_reparation)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """, (date, heure, emplacement, site, surface_affectee_m2, debit_estime_lmin, couleur_eau, gravite, action_corrective, responsable, commentaires, date_reparation))
    conn.commit()
    cur.close()
    conn.close()
    # Emit without the broadcast argument.
    socketio.emit('update_table', {'table': 'suintement'})
    return redirect(url_for('wall'))

@app.route('/insert_tuyauterie', methods=['POST'])
def insert_tuyauterie():
    date = request.form.get('tuyauterie_date')
    heure = request.form.get('tuyauterie_heure')
    emplacement = request.form.get('tuyauterie_emplacement')
    site = request.form.get('tuyauterie_site')
    type_tuyauterie = request.form.get('tuyauterie_type')
    profondeur_estimee_cm = request.form.get('tuyauterie_profondeur')
    diametre_mm = request.form.get('tuyauterie_diametre')
    gravite = request.form.get('tuyauterie_gravite')
    action_corrective = request.form.get('tuyauterie_action')
    responsable = request.form.get('tuyauterie_responsable')
    commentaires = request.form.get('tuyauterie_commentaires')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO preuve_tuyauterie
          (date, heure, emplacement, site, type_tuyauterie, profondeur_estimee_cm, diametre_mm, gravite, action_corrective, responsable, commentaires)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """, (date, heure, emplacement, site, type_tuyauterie, profondeur_estimee_cm, diametre_mm, gravite, action_corrective, responsable, commentaires))
    conn.commit()
    cur.close()
    conn.close()
    socketio.emit('update_table', {'table': 'tuyauterie'})
    return redirect(url_for('wall'))
    
@app.route('/insert_erosion', methods=['POST'])
def insert_erosion():
    date = request.form.get('erosion_date')
    heure = request.form.get('erosion_heure')
    emplacement = request.form.get('erosion_emplacement')
    site = request.form.get('erosion_site')
    zone_erodee_m2 = request.form.get('erosion_zone')
    profondeur_erosion_cm = request.form.get('erosion_profondeur')
    type_erosion = request.form.get('erosion_type')
    gravite = request.form.get('erosion_gravite')
    action_corrective = request.form.get('erosion_action')
    responsable = request.form.get('erosion_responsable')
    commentaires = request.form.get('erosion_commentaires')
    statut = request.form.get('erosion_statut')
    date_reparation = request.form.get('erosion_date_reparation')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO preuve_erosion
          (date, heure, emplacement, site, zone_erodee_m2, profondeur_erosion_cm, type_erosion, gravite, action_corrective, responsable, commentaires, statut, date_reparation)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """, (date, heure, emplacement, site, zone_erodee_m2, profondeur_erosion_cm, type_erosion, gravite, action_corrective, responsable, commentaires, statut, date_reparation))
    conn.commit()
    cur.close()
    conn.close()
    socketio.emit('update_table', {'table': 'erosion'})
    return redirect(url_for('wall'))

@app.route('/insert_fissuration', methods=['POST'])
def insert_fissuration():
    date = request.form.get('fissuration_date')
    heure = request.form.get('fissuration_heure')
    emplacement = request.form.get('fissuration_emplacement')
    site = request.form.get('fissuration_site')
    type_fissure = request.form.get('fissuration_type_fissure')
    longueur_m = request.form.get('fissuration_longueur')
    largeur_mm = request.form.get('fissuration_largeur')
    profondeur_cm = request.form.get('fissuration_profondeur')
    signes_glissement = request.form.get('fissuration_signes') == 'on'
    gravite = request.form.get('fissuration_gravite')
    action_corrective = request.form.get('fissuration_action')
    responsable = request.form.get('fissuration_responsable')
    commentaires = request.form.get('fissuration_commentaires')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO preuve_fissuration_glissement
          (date, heure, emplacement, site, type_fissure, longueur_m, largeur_mm, profondeur_cm, signes_glissement, gravite, action_corrective, responsable, commentaires)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """, (date, heure, emplacement, site, type_fissure, longueur_m, largeur_mm, profondeur_cm, signes_glissement, gravite, action_corrective, responsable, commentaires))
    conn.commit()
    cur.close()
    conn.close()
    socketio.emit('update_table', {'table': 'fissuration'})
    return redirect(url_for('wall'))


# Fetch data from the precipitation_measures table
def fetch_sites2():
    """Fetch unique site names from all three tables."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        query = """
          SELECT DISTINCT sites FROM precipitation_measures
          UNION
          SELECT DISTINCT sites FROM weather_conditions
          UNION
          SELECT DISTINCT sites FROM reservoir_status;
        """
        cur.execute(query)
        records = cur.fetchall()
        # Extract site names from the records (filtering out potential nulls)
        sites = [row[0] for row in records if row[0]]
        cur.close()
        conn.close()
        return sites
    except Exception as e:
        print("Error fetching sites:", e)
        if conn:
            conn.close()
        return []

def fetch_precipitation_data(site=None):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
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
        records = cur.fetchall()
        cur.close()
        conn.close()
        return records
    except Exception as e:
        print(f"Error fetching precipitation data: {e}")
        if conn:
            conn.close()
        flash(f"An error occurred while fetching precipitation data: {e}")
        return []

def fetch_weather_data(site=None):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
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
        records = cur.fetchall()
        cur.close()
        conn.close()
        return records
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        if conn:
            conn.close()
        flash(f"An error occurred while fetching weather data: {e}")
        return []

def fetch_reservoir_data(site=None):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
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
        records = cur.fetchall()
        cur.close()
        conn.close()
        return records
    except Exception as e:
        print(f"Error fetching reservoir data: {e}")
        if conn:
            conn.close()
        flash(f"An error occurred while fetching reservoir data: {e}")
        return []

@app.route('/water_management', methods=['GET', 'POST'])
def water_management():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        try:
            date_str = request.form['date']
            time_str = request.form['time']
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            # Get the site value from the submitted form data.
            site = request.form['site']

            if form_type == 'precipitation':
                precipitation_volume_mm = float(request.form['precipitation_volume_mm'])
                precipitation_duration_hours = float(request.form['precipitation_duration_hours'])
                precipitation_type = request.form['precipitation_type']
                impact_on_dike = request.form['impact_on_dike']
                corrective_action = request.form['corrective_action']
                responsible = request.form['responsible']
                comments = request.form['comments']

                conn = get_db_connection()
                if conn is None:
                    raise Exception("Database connection failed.")
                cur = conn.cursor()
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
                new_record = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()

            elif form_type == 'weather':
                temperature_c = float(request.form['temperature_c'])
                wind_speed_kmh = float(request.form['wind_speed_kmh'])
                wind_direction = request.form['wind_direction']
                relative_humidity_percent = float(request.form['relative_humidity_percent'])
                potential_impact = request.form['potential_impact']
                severity = request.form['severity']
                corrective_action = request.form['corrective_action']
                responsible = request.form['responsible']

                conn = get_db_connection()
                if conn is None:
                    raise Exception("Database connection failed.")
                cur = conn.cursor()
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
                new_record = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()

            elif form_type == 'reservoir':
                freeboard_m = float(request.form['freeboard_m'])
                current_volume_m3 = float(request.form['current_volume_m3'])
                max_volume_m3 = float(request.form['max_volume_m3'])
                fill_percentage = float(request.form['fill_percentage'])
                estimated_time_to_fill_days = float(request.form['estimated_time_to_fill_days'])
                required_action = request.form['required_action']
                responsible = request.form['responsible']
                comments = request.form['comments']

                conn = get_db_connection()
                if conn is None:
                    raise Exception("Database connection failed.")
                cur = conn.cursor()
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
                cur.close()
                conn.close()

            # Redirect after a successful insertion.
            return redirect(url_for('water_management'))

        except Exception as e:
            traceback.print_exc()
            error_message = f"An error occurred while inserting data: {e}"
            flash(error_message)
            return redirect(url_for('water_management'))

    else:
        # Get the site filter value from the URL parameters; default is "all"
        site_filter = request.args.get('site', 'all')
        precipitation_data = fetch_precipitation_data(site_filter)
        weather_data = fetch_weather_data(site_filter)
        reservoir_data = fetch_reservoir_data(site_filter)
        sites = fetch_sites2()  # Get the unique list of site names from the database

        return render_template('water_management.html',
                               precipitation_data=precipitation_data,
                               weather_data=weather_data,
                               reservoir_data=reservoir_data,
                               selected_site=site_filter,
                               sites=sites)


# Fetch data from the Discharge_Fluid_Clarity table
# Fetch data from the Discharge_Fluid_Clarity table
def fetch_discharge_fluid_clarity_data():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return []
    try:
        cur = conn.cursor()
        select_query = """
            SELECT date, time, location, fluid_clarity, turbidity, observed_color, flow_rate,
                   corrective_action, responsible_person, comments, sites
            FROM Discharge_Fluid_Clarity
            ORDER BY date DESC, time DESC;
        """
        cur.execute(select_query)
        records = cur.fetchall()
        cur.close()
        conn.close()
        return records
    except Exception as e:
        print(f"Error fetching discharge fluid clarity data: {e}")
        if conn:
            conn.close()
        flash(f"An error occurred while fetching discharge fluid clarity data: {e}")
        return []

# Fetch data from the Leak_Signs table
def fetch_leak_signs_data():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return []
    try:
        cur = conn.cursor()
        select_query = """
            SELECT date, time, leak_location, estimated_flow_rate, exact_location, corrective_action,
                   repair_date, responsible_person, comments, sites
            FROM Leak_Signs
            ORDER BY date DESC, time DESC;
        """
        cur.execute(select_query)
        records = cur.fetchall()
        cur.close()
        conn.close()
        return records
    except Exception as e:
        print(f"Error fetching leak signs data: {e}")
        if conn:
            conn.close()
        flash(f"An error occurred while fetching leak signs data: {e}")
        return []

# Fetch data from the Structural_Integrity_Water_Recovery table
def fetch_structural_integrity_data():
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database.")
        return []
    try:
        cur = conn.cursor()
        select_query = """
            SELECT date, time, location, structure_condition, signs_of_corrosion, observed_deformation,
                   current_performance, corrective_action, responsible_person, comments, sites
            FROM Structural_Integrity_Water_Recovery
            ORDER BY date DESC, time DESC;
        """
        cur.execute(select_query)
        records = cur.fetchall()
        cur.close()
        conn.close()
        return records
    except Exception as e:
        print(f"Error fetching structural integrity data: {e}")
        if conn:
            conn.close()
        flash(f"An error occurred while fetching structural integrity data: {e}")
        return []

# Route for the water_recovery page
@app.route('/water_recovery', methods=['GET', 'POST'])
def water_recovery():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        try:
            # Retrieve common form data
            date_str = request.form['date']
            time_str = request.form['time']
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.strptime(time_str, '%H:%M').time()

            if form_type == 'discharge_fluid_clarity':
                location = request.form['location']
                fluid_clarity = request.form['fluid_clarity']
                turbidity = int(request.form['turbidity'])
                observed_color = request.form['observed_color']
                flow_rate = float(request.form['flow_rate'])
                corrective_action = request.form['corrective_action']
                responsible_person = request.form['responsible_person']
                comments = request.form['comments']
                site = request.form['sites']  # Ensure form field name is "sites"

                # Insert into Discharge_Fluid_Clarity table
                conn = get_db_connection()
                if conn is None:
                    raise Exception("Database connection failed.")
                cur = conn.cursor()
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
                new_record = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()

            elif form_type == 'leak_signs':
                leak_location = request.form['leak_location']
                estimated_flow_rate = float(request.form['estimated_flow_rate'])
                exact_location = request.form['exact_location']
                corrective_action = request.form['corrective_action']
                repair_date = request.form.get('repair_date')
                responsible_person = request.form['responsible_person']
                comments = request.form['comments']
                site = request.form['sites']

                # Insert into Leak_Signs table
                conn = get_db_connection()
                if conn is None:
                    raise Exception("Database connection failed.")
                cur = conn.cursor()
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
                new_record = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()

            elif form_type == 'structural_integrity':
                location = request.form['location']
                structure_condition = request.form['structure_condition']
                signs_of_corrosion = request.form['signs_of_corrosion']
                observed_deformation = request.form['observed_deformation']
                current_performance = float(request.form['current_performance'])
                corrective_action = request.form['corrective_action']
                responsible_person = request.form['responsible_person']
                comments = request.form['comments']
                site = request.form['sites']

                # Insert into Structural_Integrity_Water_Recovery table
                conn = get_db_connection()
                if conn is None:
                    raise Exception("Database connection failed.")
                cur = conn.cursor()
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
                cur.close()
                conn.close()

            # Redirect to prevent form resubmission
            return redirect(url_for('water_recovery'))

        except Exception as e:
            traceback.print_exc()
            error_message = f"An error occurred while inserting data: {e}"
            flash(error_message)
            return redirect(url_for('water_recovery'))

    else:
        # Fetch data from each table
        discharge_fluid_clarity_data = fetch_discharge_fluid_clarity_data()
        leak_signs_data = fetch_leak_signs_data()
        structural_integrity_data = fetch_structural_integrity_data()

        # Collect unique site names from all records (assuming the site value is
        # stored in the last column of each record)
        sites_set = set()
        for record in discharge_fluid_clarity_data:
            sites_set.add(record[-1])
        for record in leak_signs_data:
            sites_set.add(record[-1])
        for record in structural_integrity_data:
            sites_set.add(record[-1])
        sites_list = sorted(list(sites_set))

        return render_template('water_recovery.html',
                               discharge_fluid_clarity_data=discharge_fluid_clarity_data,
                               leak_signs_data=leak_signs_data,
                              structural_integrity_data=structural_integrity_data,
                               sites=sites_list)
if __name__ == '__main__':
    socketio.run(app, debug=True)  # Use socketio.run instead of app.run