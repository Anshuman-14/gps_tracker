from flask import Flask, request, jsonify, render_template
from datetime import datetime
import sqlite3

app = Flask(__name__, template_folder='templates')

DB_NAME = "location.db"

# Initialize database with device_id as PRIMARY KEY
def init_db():
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            device_id TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            timestamp TEXT
        )
        """)

@app.route('/')
def home():
    return '🚀 GPS Tracking Server is Running!'

@app.route('/map')
def map_page():
    return render_template("index.html")

@app.route('/api/location', methods=['GET', 'POST'])
def save_location():
    if request.method == 'POST':
        lat = request.form.get("lat")
        lon = request.form.get("lon")
        device_id = request.form.get("id")
    else:
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        device_id = request.args.get("id")

    ts = datetime.now().isoformat()

    if lat and lon and device_id:
        try:
            with sqlite3.connect(DB_NAME) as con:
                con.execute("""
                    INSERT OR REPLACE INTO locations (device_id, latitude, longitude, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (device_id, lat, lon, ts))
            return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "Missing lat, lon, or id"}), 400

@app.route('/api/locations', methods=['GET'])
def get_all_locations():
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM locations ORDER BY timestamp DESC")
        rows = cur.fetchall()
        devices = [
            {"device_id": r[0], "latitude": r[1], "longitude": r[2], "timestamp": r[3]}
            for r in rows
        ]
    return jsonify(devices)

@app.route('/api/all', methods=['GET'])
def all_locations():
    conn = sqlite3.connect('gps_data.db')  # optional if you use this table separately
    c = conn.cursor()
    c.execute('SELECT id, latitude, longitude FROM gps')
    rows = c.fetchall()
    conn.close()

    result = [{'id': row[0], 'latitude': row[1], 'longitude': row[2]} for row in rows]
    return jsonify(result)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
