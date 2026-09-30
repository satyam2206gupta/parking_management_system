from datetime import datetime
import os

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

# --------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------

# Render can provide DATABASE_URL as an environment variable.
# If it is not available, SQLite is used for local testing.
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Render/PostgreSQL URLs may start with postgres://
    # SQLAlchemy now expects postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///parking.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------------------------------------
# PARKING SETTINGS
# --------------------------------------------------

HOURLY_RATE = 50.00


# --------------------------------------------------
# DATABASE MODELS
# --------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )


class ParkingSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    slot_number = db.Column(
        db.String(10),
        unique=True,
        nullable=False
    )

    vehicle_number = db.Column(
        db.String(20),
        nullable=True
    )

    vehicle_type = db.Column(
        db.String(20),
        nullable=True
    )

    entry_time = db.Column(
        db.DateTime,
        nullable=True
    )

    status = db.Column(
        db.String(20),
        default="Available"
    )


class ParkingHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    vehicle_number = db.Column(
        db.String(20),
        nullable=False
    )

    vehicle_type = db.Column(
        db.String(20),
        nullable=False
    )

    slot_number = db.Column(
        db.String(10),
        nullable=False
    )

    entry_time = db.Column(
        db.String(30),
        nullable=False
    )

    exit_time = db.Column(
        db.String(30),
        nullable=False
    )

    duration_hours = db.Column(
        db.Float,
        nullable=False
    )

    fee = db.Column(
        db.Float,
        nullable=False
    )


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def initialize_database():
    with app.app_context():

        db.create_all()

        # Create 20 parking slots only if none exist
        if ParkingSlot.query.count() == 0:

            for i in range(1, 21):

                db.session.add(
                    ParkingSlot(
                        slot_number=f"SLOT-{i:02d}",
                        status="Available"
                    )
                )

            db.session.commit()


initialize_database()


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------
# SIGNUP
# --------------------------------------------------

@app.route("/api/signup", methods=["POST"])
def signup():

    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:

        return jsonify({
            "error": "Username and password required"
        }), 400

    existing_user = User.query.filter_by(
        username=username
    ).first()

    if existing_user:

        return jsonify({
            "error": "Username already exists!"
        }), 400

    new_user = User(
        username=username,
        password=password
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "Account created successfully! Please login."
    })


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    user = User.query.filter_by(
        username=username,
        password=password
    ).first()

    if user:

        return jsonify({
            "message": "Login successful",
            "username": user.username
        })

    return jsonify({
        "error": "Invalid username or password"
    }), 401


# --------------------------------------------------
# GET ALL PARKING SLOTS
# --------------------------------------------------

@app.route("/api/slots", methods=["GET"])
def get_slots():

    slots = ParkingSlot.query.order_by(
        ParkingSlot.id
    ).all()

    result = []

    for slot in slots:

        result.append({
            "id": slot.id,
            "slot_number": slot.slot_number,
            "vehicle_number": slot.vehicle_number,
            "vehicle_type": slot.vehicle_type,
            "entry_time": (
                slot.entry_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if slot.entry_time
                else None
            ),
            "status": slot.status
        })

    return jsonify(result)


# --------------------------------------------------
# PARK VEHICLE
# --------------------------------------------------

@app.route("/api/park", methods=["POST"])
def park_vehicle():

    data = request.get_json(silent=True) or {}

    slot_id = data.get("slot_id")
    vehicle_number = data.get(
        "vehicle_number",
        ""
    ).strip().upper()

    vehicle_type = data.get(
        "vehicle_type",
        ""
    ).strip()

    if not slot_id or not vehicle_number or not vehicle_type:

        return jsonify({
            "error": "Slot, vehicle number and type are required"
        }), 400

    slot = db.session.get(
        ParkingSlot,
        slot_id
    )

    if not slot:

        return jsonify({
            "error": "Parking slot not found"
        }), 404

    if slot.status == "Occupied":

        return jsonify({
            "error": "Selected slot is already occupied!"
        }), 400

    existing = ParkingSlot.query.filter_by(
        vehicle_number=vehicle_number,
        status="Occupied"
    ).first()

    if existing:

        return jsonify({
            "error":
                f"Vehicle {vehicle_number} is already inside parked."
        }), 400

    slot.vehicle_number = vehicle_number
    slot.vehicle_type = vehicle_type
    slot.entry_time = datetime.now()
    slot.status = "Occupied"

    db.session.commit()

    return jsonify({
        "message":
            f"Vehicle parked successfully in {slot.slot_number}"
    })


# --------------------------------------------------
# VEHICLE EXIT
# --------------------------------------------------

@app.route("/api/exit/<int:slot_id>", methods=["POST"])
def vehicle_exit(slot_id):

    slot = db.session.get(
        ParkingSlot,
        slot_id
    )

    if not slot:

        return jsonify({
            "error": "Parking slot not found"
        }), 404

    if slot.status == "Available":

        return jsonify({
            "error": "Slot is already empty"
        }), 400

    if not slot.entry_time:

        return jsonify({
            "error": "Entry time is missing"
        }), 400

    exit_time = datetime.now()

    duration_hours = (
        exit_time - slot.entry_time
    ).total_seconds() / 3600.0

    # Minimum charge = ₹50
    charge = max(
        round(duration_hours * HOURLY_RATE, 2),
        HOURLY_RATE
    )

    history = ParkingHistory(

        vehicle_number=slot.vehicle_number,

        vehicle_type=slot.vehicle_type,

        slot_number=slot.slot_number,

        entry_time=slot.entry_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        exit_time=exit_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        duration_hours=round(
            duration_hours,
            2
        ),

        fee=charge
    )

    db.session.add(history)

    vehicle_number = slot.vehicle_number

    # Free the slot
    slot.vehicle_number = None
    slot.vehicle_type = None
    slot.entry_time = None
    slot.status = "Available"

    db.session.commit()

    return jsonify({

        "message":
            f"Vehicle {vehicle_number} checked out.",

        "duration_hours":
            round(duration_hours, 2),

        "fee":
            charge
    })


# --------------------------------------------------
# PARKING HISTORY
# --------------------------------------------------

@app.route("/api/history", methods=["GET"])
def get_history():

    history = ParkingHistory.query.order_by(
        ParkingHistory.id.desc()
    ).all()

    total_revenue = sum(
        item.fee
        for item in history
    )

    history_list = []

    for item in history:

        history_list.append({

            "vehicle_number":
                item.vehicle_number,

            "vehicle_type":
                item.vehicle_type,

            "slot_number":
                item.slot_number,

            "entry_time":
                item.entry_time,

            "exit_time":
                item.exit_time,

            "duration_hours":
                item.duration_hours,

            "fee":
                item.fee
        })

    return jsonify({

        "history":
            history_list,

        "total_revenue":
            round(total_revenue, 2)
    })


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():

    return jsonify({
        "status": "OK",
        "application": "Smart Parking Management System"
    })


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )