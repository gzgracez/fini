from sql import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
import re
import requests

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///fini.db")

@app.route("/")
@login_required
def index():

    # load user's preferences
    q_prefs = db.execute("SELECT ticker FROM userCompany INNER JOIN companies ON idCompany = id WHERE idUser = :idUser", idUser = session["user_id"])
    q_prefs += db.execute("SELECT name FROM userIndustry INNER JOIN industries ON idIndustry = id WHERE idUser = :idUser", idUser = session["user_id"])
    g_prefs = db.execute("SELECT name FROM userGeography INNER JOIN geographies ON idGeography = id WHERE idUser = :idUser", idUser = session["user_id"])

    # if user has no preferences, render default selection
    if len(q_prefs) == 0 and len(g_prefs) == 0:
        news = lookupArticles(topic="b")
        return render_template("index.html", news=news)

    
    # iteratively load user company and industry preferences into query for lookupArticles
    q = ""
    if len(q_prefs) > 0:
        for i in q_prefs:
            q += i["name"] + "+OR+"
        q = q[:-3]

    # iteratively load user company and industry preferences into query for lookupArticles
    geo = ""
    if len(g_prefs) > 0:
        for i in g_prefs:
            geo += i["name"] + "OR"
        geo = geo[:-2]

    print(q)

    news = lookupArticles(geo=geo, q=q)
    print(q)
    return render_template("index.html", news=news)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username")
            return render_template("login.html")

        # ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return render_template("login.html")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        
        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            flash("Invalid username and/or password")
            return render_template("login.html")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username")
            return render_template("register.html")

        # ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return render_template("register.html")
            
        # ensure password was confirmed
        elif not request.form.get("confirmation"):
            flash("Must confirm password")
            return render_template("register.html")
            
        # ensure confirmed password is the same
        elif request.form.get("confirmation") != request.form.get("password"):
            flash("Confirmed password does not match!")
            return render_template("register.html")

        # check username doesn't already exist
        repeated = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(repeated) > 0:
            flash("Username is already taken!")
            return render_template("register.html")
            
        # query database for username
        rows = db.execute("INSERT INTO users (username, hash) VALUES (:username, :pwhash)", 
                                username=request.form.get("username"), 
                                pwhash=pwd_context.encrypt(request.form.get("password")))
        
        # remember which user has logged in
        session["user_id"] = rows

        # redirect user to home page
        flash("Registered!")
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    """Search for company, industry or geography"""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # check that user input prompt
        if not request.form.get("prompt"):
            flash("Must provide search criteria")
            return render_template("search.html")

        # redirect based on button
        if request.form.get("button") == "company":
            
            stock = lookup(request.form.get("prompt"))
            
            if stock == None:
                flash("Symbol not found")
                return render_template("search.html")
            
            # check whether user follow's company
            # get company id
            idCompany = db.execute("SELECT id FROM companies WHERE name = :name", name = stock["name"])

            # if company is not in database, add it and get id
            if len(idCompany) == 0:
                idCompany = db.execute("INSERT INTO companies (name) VALUES (:name)", name = stock["name"])
            else:
                idCompany = idCompany[0]["id"]

            # check if company is in user's interest
            rows = db.execute("SELECT * FROM userCompany WHERE idUser = :idUser AND idCompany = :idCompany", idUser = session["user_id"], idCompany = idCompany)

            if len(rows) == 0:
                followed = False
            else:
                followed = True

            return render_template("results_comp.html", stock = stock, idCompany = idCompany, followed = followed, news = lookupArticles(q=request.form.get("prompt"))[:5])

        if request.form.get("button") == "industry":

            name = request.form.get("prompt").capitalize()

            # check whether user follow's company
            # get company id
            idIndustry = db.execute("SELECT id FROM industries WHERE name = :name", name = name)

            # if company is not in database, add it and get id
            if len(idIndustry) == 0:
                idIndustry = db.execute("INSERT INTO industries (name) VALUES (:name)", name = name)
            else:
                idIndustry = idIndustry[0]["id"]

            # check if company is in user's interest
            rows = db.execute("SELECT * FROM userIndustry WHERE idUser = :idUser AND idIndustry = :idIndustry", idUser = session["user_id"], idIndustry = idIndustry)

            if len(rows) == 0:
                followed = False
            else:
                followed = True

            return render_template("results.html", title="Industry: " + request.form.get("prompt").capitalize(), idGroup = idIndustry, group = "industry", followed = followed, news = lookupArticles(q=request.form.get("prompt")))

        if request.form.get("button") == "geography":
            return render_template("results.html", title="Geography: " + request.form.get("prompt").capitalize(), news = lookupArticles(geo=request.form.get("prompt")))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("search.html")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Change account settings"""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if request.form.get("btn") == "username":

            # ensure all fields were filled
            if not request.form.get("username"):
                flash("Username required")
                return render_template("account.html")
            
            # update username
            db.execute("UPDATE users SET username = :username WHERE id = :id", username = request.form.get("username"), id = session["user_id"])
            flash("Username Changed!")

        if request.form.get("btn") == "password":

            # ensure all fields were filled
            if not request.form.get("old") or not request.form.get("new") or not request.form.get("newr"):
                flash("All fields required")
                return render_template("account.html")
                
            old = request.form.get("old")
            new = request.form.get("new")
            newr = request.form.get("newr")
                
            # check old password
            if not pwd_context.verify(request.form.get("old"), db.execute("SELECT hash FROM users WHERE id = :id",
                id = session["user_id"])[0]["hash"]):
                    flash("Incorrect previous password")
                    return render_template("account.html")
                
            # check that new passwords match
            elif new != newr:
                flash("Passwords do not match")
                return render_template("account.html")
            
            # update password
            db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash = pwd_context.encrypt(new), id = session["user_id"])
            flash("Password Changed!")
        # return to password window
        
        return render_template("account.html")
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("account.html")

@app.route("/followUpdate", methods=["POST"])
@login_required
def followUpdate():
    """Add/remove to/from interests."""
    if request.args.get('id') and request.args.get('follow'):
        group = request.args.get('gr')
        if request.args.get('follow') == "true":
            db.execute("INSERT INTO user" + group + " (idUser, id" + group + ") VALUES (:idUser, :id)", idUser = session["user_id"], id = request.args.get('id'))
            print("INSERTED")
        else:
            db.execute("DELETE FROM user" + group + " WHERE idUser=:idUser AND id" + group + "=:id", idUser = session["user_id"], id = request.args.get('id'))
            print("DELETED")
    return "update"
    
@app.route("/preferences")
def preferences():
    """View/remove preferences."""

    userCompany = db.execute("SELECT idCompany, name FROM userCompany INNER JOIN companies ON idCompany = id WHERE idUser = :idUser ORDER BY name ASC", idUser = session["user_id"])
    userIndustry = db.execute("SELECT idIndustry, name FROM userIndustry INNER JOIN industries ON idIndustry = id WHERE idUser = :idUser ORDER BY name ASC", idUser = session["user_id"])
    userGeography = db.execute("SELECT idGeography, name FROM userGeography INNER JOIN geographies ON idGeography = id WHERE idUser = :idUser ORDER BY name ASC", idUser = session["user_id"])
    return render_template("preferences.html", userCompany = userCompany, userIndustry = userIndustry, userGeography = userGeography)
