from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table
import os

app = Flask(__name__)
app.secret_key = "super_secret_key"

# DB
def db():
    conn = sqlite3.connect("data.db")
    conn.row_factory = sqlite3.Row
    return conn

# INIT DB
def init():
    conn = db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        company_name TEXT,
        login TEXT,
        password TEXT,
        role TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS boxes (
        id INTEGER PRIMARY KEY,
        company_id INTEGER,
        box_number TEXT,
        location TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY,
        company_id INTEGER,
        box_id INTEGER,
        name TEXT,
        left_qty INTEGER,
        expiry_date TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY,
        company_id INTEGER,
        medicine TEXT,
        qty INTEGER,
        person TEXT,
        created_at TEXT
    )""")

    conn.commit()
    conn.close()

init()

# LOGIN
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        password = request.form["password"]

        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE login=? AND password=?",
            (login, password)
        ).fetchone()

        if user:
            session["company_id"] = user["id"]
            session["role"] = user["role"]
            session["company_name"] = user["company_name"]
            return redirect("/dashboard")

    return render_template("login.html")


# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "company_id" not in session:
        return redirect("/")

    conn = db()

    meds = conn.execute("""
        SELECT * FROM medicines
        WHERE company_id=?
    """, (session["company_id"],)).fetchall()

    # ALERT CHECK
    alerts = []
    for m in meds:
        if m["left_qty"] <= 5:
            alerts.append(f"⚠ {m['name']} kam qolgan!")
        if m["expiry_date"]:
            alerts.append(f"⏳ {m['name']} srogi nazoratda")

    return render_template("dashboard.html", meds=meds, alerts=alerts)


# ADD MED
@app.route("/add", methods=["POST"])
def add():
    conn = db()

    conn.execute("""
        INSERT INTO medicines(company_id,name,left_qty,expiry_date)
        VALUES (?,?,?,?)
    """, (
        session["company_id"],
        request.form["name"],
        request.form["qty"],
        request.form["expiry"]
    ))

    conn.commit()
    return redirect("/dashboard")


# GIVE MED
@app.route("/give", methods=["POST"])
def give():
    conn = db()

    med = conn.execute(
        "SELECT * FROM medicines WHERE id=?",
        (request.form["med_id"],)
    ).fetchone()

    qty = int(request.form["qty"])

    if med and med["left_qty"] >= qty:
        conn.execute(
            "UPDATE medicines SET left_qty=? WHERE id=?",
            (med["left_qty"] - qty, med["id"])
        )

        conn.execute("""
            INSERT INTO logs(company_id,medicine,qty,person,created_at)
            VALUES (?,?,?,?,datetime('now'))
        """, (
            session["company_id"],
            med["name"],
            qty,
            request.form["person"]
        ))

        conn.commit()

    return redirect("/dashboard")


# EXCEL EXPORT
@app.route("/excel")
def excel():
    conn = db()

    df = pd.read_sql_query("""
        SELECT name,left_qty,expiry_date
        FROM medicines
        WHERE company_id=?
    """, conn, params=(session["company_id"],))

    file = "hisobot.xlsx"
    df.to_excel(file, index=False)

    return send_file(file, as_attachment=True)


# PDF EXPORT
@app.route("/pdf")
def pdf():
    conn = db()

    data = conn.execute("""
        SELECT name,left_qty,expiry_date
        FROM medicines
        WHERE company_id=?
    """, (session["company_id"],)).fetchall()

    file = "hisobot.pdf"
    doc = SimpleDocTemplate(file)

    table = [["Dori","Qoldiq","Srogi"]]
    for r in data:
        table.append([r["name"], r["left_qty"], r["expiry_date"]])

    doc.build([Table(table)])

    return send_file(file, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
