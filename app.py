from flask import Flask, request, jsonify, render_template, redirect, url_for
from datetime import datetime
import sqlite3
import math

app = Flask(__name__, template_folder='templates')

DB_NAME = "location.db"

def init_db():
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS current_location (
            device_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100),
            latitude DOUBLE,
            longitude DOUBLE,
            nearest_landmark VARCHAR(100),
            battery VARCHAR(20),
            timestamp DATETIME
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS officers (
            officer_id VARCHAR(50) PRIMARY KEY,
            officer_name VARCHAR(100),
            officer_contact VARCHAR(20),
            device_name VARCHAR(100),
            device_contact VARCHAR(20)
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS landmarks (
            landmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100),
            latitude DOUBLE,
            longitude DOUBLE
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS access (
            officer_id VARCHAR(50),
            officer_name VARCHAR(100),
            user_name VARCHAR(50),
            password VARCHAR(255),
            PRIMARY KEY (user_name)
        );
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS allotment (
            officer_id VARCHAR(100),
            device_id  VARCHAR(100),
            PRIMARY KEY (officer_id, device_id)
        );
        """)

        cur = con.cursor()
        cur.execute("SELECT 1 FROM access WHERE officer_name = 'admin'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO access (officer_id, officer_name, user_name, password)
                VALUES (?, ?, ?, ?)
            """, ('','admin', 'admin', 'admin'))



################################################## Functions ###################################################################


def haversine(lat1, lon1, lat2, lon2):
    # Radius of Earth in km
    R = 6371.0
    # Convert degrees to radians
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Haversine formula
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # Distance in kilometers

def update_nearest_landmarks():
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()

        # Get all landmarks
        cur.execute("SELECT landmark_id, name, latitude, longitude FROM landmarks")
        landmarks = cur.fetchall()

        if not landmarks:
            print("No landmarks found.")
            return

        # Get all device locations
        cur.execute("SELECT device_id, latitude, longitude FROM current_location")
        devices = cur.fetchall()

        for device_id, d_lat, d_lon in devices:
            nearest_name = None
            nearest_distance = float('inf')

            for landmark_id, name, l_lat, l_lon in landmarks:
                distance = haversine(d_lat, d_lon, l_lat, l_lon)
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_name = name

            # Update nearest landmark for the device
            if nearest_name:
                cur.execute(
                    "UPDATE current_location SET nearest_landmark=? WHERE device_id=?",
                    (nearest_name, device_id)
                )

        con.commit()
        print("Nearest landmarks updated for all devices.")

#################################################### Routes ###################################################################
@app.route('/')
def home():
    return '🚀 GPS Tracking Server is Running!'

@app.route('/api/landmarks')
def get_landmarks():
    import sqlite3
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        rows = cur.execute("SELECT name, latitude, longitude FROM landmarks").fetchall()
    return jsonify([
        {'name': name, 'lat': lat, 'lng': lng} for name, lat, lng in rows
    ])

@app.route('/map')
def map_page():
    return render_template("index.html")

@app.route('/api/location', methods=['GET', 'POST'])
def save_location():
    lat = request.values.get("lat")
    lon = request.values.get("lon")
    battery = request.values.get("battery")
    device_id = request.values.get("id")
    ts = datetime.now().isoformat()

    if lat and lon and device_id:
        try:
            with sqlite3.connect(DB_NAME) as con:
                cur = con.cursor()
                cur.execute("SELECT device_id FROM current_location WHERE device_id = ?", (device_id,))
                existing = cur.fetchone()

                if existing:
                    cur.execute("""
                        UPDATE current_location
                        SET latitude = ?, longitude = ?, battery = ?, timestamp = ?
                        WHERE device_id = ?
                    """, (lat, lon, battery, ts, device_id))
                else:
                    cur.execute("""
                        INSERT INTO current_location (device_id, latitude, longitude, battery, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, (device_id, lat, lon, battery, ts))

                con.commit()
            return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error", "message": "Missing lat, lon, or id"}), 400


@app.route('/api/locations')
def get_all_locations():
    update_nearest_landmarks()
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT device_id, name, latitude, longitude, nearest_landmark, battery, timestamp 
            FROM current_location ORDER BY timestamp DESC
        """)
        rows = cur.fetchall()
    devices = [
        {
            "device_id": r[0],
            "name": r[1],
            "latitude": r[2],
            "longitude": r[3],
            "landmark": r[4],
            "battery": r[5],
            "timestamp": r[6]
        } for r in rows
    ]
    return jsonify(devices)

login_state = {
    'admin_logged_in': False,
    'user_logged_in': False,
    'officer_name': '',
    'device_ids': ''
}
@app.route('/login', methods=['GET', 'POST'])
def login():
    global login_state

    if request.method == 'POST':
        user_name = request.form['user_name']
        password = request.form['password']

        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            cur.execute("SELECT officer_id, officer_name FROM access WHERE user_name=? AND password=?", (user_name, password))
            user = cur.fetchone()

        if user is None:
            return render_template('login.html', error='Invalid credentials')

        officer_id, officer_name = user
        login_state['officer_name'] = officer_name
        login_state['officer_id'] = officer_id

        if officer_name.strip().lower() == 'admin':
            login_state['admin_logged_in'] = True
            login_state['user_logged_in'] = False  # reset just in case
            return redirect(url_for('admin_panel'))
        else:
            login_state['user_logged_in'] = True
            login_state['admin_logged_in'] = False
            return redirect(url_for('user_dashboard'))

    return render_template('login.html')


@app.route('/admin')
def admin_panel():
    if not login_state['admin_logged_in']:
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/dashboard')
def user_dashboard():
    if not login_state.get('user_logged_in'):
        print("User not logged in.")
        return redirect(url_for('login'))

    officer_name = login_state.get('officer_name', '')
    officer_id = login_state.get('officer_id', '')

    if not officer_id:
        print("Missing officer_id.")
        return redirect(url_for('login'))  # fallback if login_state isn't properly set

    print(f"[DEBUG] Officer ID: {officer_id} - Officer Name: {officer_name}")

    # Step 1: Get assigned device IDs
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        cur.execute("SELECT device_id FROM allotment WHERE officer_id=?", (officer_id,))
        device_rows = cur.fetchall()

    device_ids = [row[0] for row in device_rows]
    print(f"[DEBUG] Device IDs assigned: {device_ids}")

    data = []
    if device_ids:
        placeholders = ','.join(['?'] * len(device_ids))
        query = f"SELECT * FROM current_location WHERE device_id IN ({placeholders})"
        print(f"[DEBUG] Query: {query}")

        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            data = cur.execute(query, device_ids).fetchall()

    print(f"[DEBUG] Data fetched: {data}")

    headers = ['device_id', 'name', 'latitude', 'longitude', 'nearest_landmark', 'battery', 'timestamp']
    return render_template('user_dashboard.html', headers=headers, data=data, officer_name=officer_name)

@app.route('/api/user_devices')
def get_user_devices():
    if not login_state.get('user_logged_in'):
        return jsonify([])

    officer_id = login_state.get('officer_id', '')
    if not officer_id:
        return jsonify([])

    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        cur.execute("SELECT device_id FROM allotment WHERE officer_id=?", (officer_id,))
        device_rows = cur.fetchall()

    device_ids = [row[0] for row in device_rows]

    if not device_ids:
        return jsonify([])

    placeholders = ','.join(['?'] * len(device_ids))
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        data = cur.execute(
            f"SELECT device_id, name, latitude, longitude, nearest_landmark FROM current_location WHERE device_id IN ({placeholders})",
            device_ids
        ).fetchall()

    result = [
        {
            'device_id': row[0],
            'name': row[1],
            'latitude': row[2],
            'longitude': row[3],
            'landmark': row[4],
        }
        for row in data
    ]
    return jsonify(result)

@app.route('/user/devices')
def user_devices():
    device_ids = request.args.get('device_ids', '')
    ids = device_ids.split(',') if device_ids else []

    if not ids:
        return "<p>No devices assigned.</p>"

    placeholders = ','.join(['?'] * len(ids))
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        data = cur.execute(f"SELECT * FROM current_location WHERE device_id IN ({placeholders})", ids).fetchall()

    headers = ['device_id', 'name', 'latitude', 'longitude', 'nearest_landmark', 'battery', 'timestamp']
    html = '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>'
    for row in data:
        html += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
    html += '</table>'
    return html

@app.route('/admin/allotment')
def admin_allotment():
    if not login_state['admin_logged_in']:
        return redirect(url_for('login'))
    with sqlite3.connect(DB_NAME) as con:
        rows = con.execute("SELECT * FROM allotment").fetchall()
    headers = ['officer_id', 'device_id']
    html = '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '<th>Actions</th></tr>'
    for row in rows:
        key = f"{row[0]}_{row[1]}"
        html += f'<tr id="row-{key}">' + ''.join(f'<td>{cell}</td>' for cell in row)
        html += f'<td><button onclick="editRow(\'allotment\', \'{key}\')">Edit</button> '
        html += f'<button onclick="deleteRow(\'allotment\', \'officer_id\', \'{row[0]}\')">Delete</button></td></tr>'
    html += '</table>'
    return html

@app.route('/admin/edit_row', methods=['POST'])
def edit_row():
    if not login_state['admin_logged_in']:
        return redirect(url_for('login'))
    data = request.json
    table = data.get('table')
    updates = data.get('updates')
    key_column = data.get('key_column')
    key_value = data.get('key_value')

    key_column2 = data.get('key_column2')
    key_value2 = data.get('key_value2')

    set_clause = ', '.join(f"{col} = ?" for col in updates if col not in (key_column, key_column2))
    values = [updates[col] for col in updates if col not in (key_column, key_column2)]

    try:
        with sqlite3.connect(DB_NAME) as con:
            if key_column2 and key_value2:
                query = f"UPDATE {table} SET {set_clause} WHERE {key_column} = ? AND {key_column2} = ?"
                values += [key_value, key_value2]
            else:
                query = f"UPDATE {table} SET {set_clause} WHERE {key_column} = ?"
                values.append(key_value)

            con.execute(query, values)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/current_location')
def admin_current_location():
    if not login_state['admin_logged_in']:
        return redirect(url_for('login'))
    with sqlite3.connect(DB_NAME) as con:
        rows = con.execute("SELECT * FROM current_location").fetchall()
    headers = ['device_id', 'name', 'latitude', 'longitude', 'nearest_landmark', 'battery', 'timestamp']
    html = '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '<th>Actions</th></tr>'
    for row in rows:
        device_id = row[0]
        html += f'<tr id="row-{device_id}">' + ''.join(f'<td>{cell}</td>' for cell in row)
        html += f'<td><button onclick="editRow(\'current_location\', \'{device_id}\')">Edit</button> <button onclick="deleteRow(\'current_location\', \'device_id\', \'{device_id}\')">Delete</button></td></tr>'
    html += '</table>'
    return html

@app.route('/admin/officers')
def admin_officers():
    if not login_state['admin_logged_in']:
        return redirect(url_for('login'))
    with sqlite3.connect(DB_NAME) as con:
        rows = con.execute("SELECT * FROM officers").fetchall()
    headers = ['officer_id', 'officer_name', 'officer_contact', 'device_name', 'device_contact']
    html = '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '<th>Actions</th></tr>'
    for row in rows:
        key = row[0]
        html += f'<tr id="row-{key}">' + ''.join(f'<td>{cell}</td>' for cell in row)
        html += f'<td><button onclick="editRow(\'officers\', \'{key}\')">Edit</button> <button onclick="deleteRow(\'officers\', \'officer_id\', \'{key}\')">Delete</button></td></tr>'
    html += '</table>'
    return html

@app.route('/admin/landmarks')
def admin_landmarks():
    if not login_state['admin_logged_in']:
        return redirect(url_for('login'))
    with sqlite3.connect(DB_NAME) as con:
        rows = con.execute("SELECT * FROM landmarks").fetchall()
    headers = ['landmark_id', 'name', 'latitude', 'longitude']
    html = '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '<th>Actions</th></tr>'
    for row in rows:
        key = str(row[0])
        html += f'<tr id="row-{key}">' + ''.join(f'<td>{cell}</td>' for cell in row)
        html += f'<td><button onclick="editRow(\'landmarks\', \'{key}\')">Edit</button> <button onclick="deleteRow(\'landmarks\', \'landmark_id\', \'{key}\')">Delete</button></td></tr>'
    html += '</table>'
    return html

@app.route('/admin/access')
def admin_access():
    if not login_state['admin_logged_in']:
        return redirect(url_for('login'))
    with sqlite3.connect(DB_NAME) as con:
        rows = con.execute("SELECT * FROM access").fetchall()
    headers = ['officer_id', 'officer_name', 'user_name', 'password']
    html = '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '<th>Actions</th></tr>'
    for row in rows:
        key = row[2]  # user_name is the key
        html += f'<tr id="row-{key}">' + ''.join(f'<td>{cell}</td>' for cell in row)
        html += f'<td><button onclick="editRow(\'access\', \'{key}\')">Edit</button> <button onclick="deleteRow(\'access\', \'user_name\', \'{key}\')">Delete</button></td></tr>'
    html += '</table>'
    return html


@app.route('/admin/delete_row', methods=['POST'])
def delete_row():
    data = request.json
    table, key_column, key_value = data['table'], data['key_column'], data['key_value']

    try:
        with sqlite3.connect(DB_NAME) as con:
            con.execute(f"DELETE FROM {table} WHERE {key_column} = ?", (key_value,))
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/update_table', methods=['POST'])
def update_table():
    data = request.get_json()
    table = data.get('table')
    values = data.get('values')

    valid_tables = {
        'current_location': ('current_location', 7),
        'officers': ('officers', 5),
        'landmarks': ('landmarks', 4),
        'access': ('access', 4),
        'allotment': ('allotment', 2)
    }

    if table not in valid_tables:
        return jsonify({'status': 'error', 'message': 'Invalid table'})

    table_name, expected_len = valid_tables[table]

    if len(values) != expected_len:
        return jsonify({'status': 'error', 'message': f'Expected {expected_len} values, got {len(values)}'})

    placeholders = ','.join(['?'] * expected_len)
    with sqlite3.connect(DB_NAME) as con:
        try:
            con.execute(f"INSERT INTO {table_name} VALUES ({placeholders})", values)
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})

@app.route('/logout')
def logout():
    global login_state
    login_state = {
        'admin_logged_in': False,
        'user_logged_in': False,
        'officer_name': '',
        'device_ids': ''
    }
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
