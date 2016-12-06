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
    """Display index news."""

    # load user's company, industry and geography preferences
    c_prefs = db.execute("SELECT ticker FROM userCompany INNER JOIN companies ON idCompany = id WHERE idUser = :idUser", idUser = session["user_id"])
    i_prefs = db.execute("SELECT name FROM userIndustry INNER JOIN industries ON idIndustry = id WHERE idUser = :idUser", idUser = session["user_id"])
    g_prefs = db.execute("SELECT name FROM userGeography INNER JOIN geographies ON idGeography = id WHERE idUser = :idUser", idUser = session["user_id"])

    # if user has no preferences, render default selection of news
    if len(c_prefs) == 0 and len(i_prefs) == 0 and len(g_prefs) == 0:
        news = lookupArticles(topic="b")
        return render_template("index.html", news=news)

    
    # iteratively load user company and industry preferences into query for lookupArticles
    q = ""
    if len(c_prefs) > 0:
        for i in c_prefs:
            q += i["ticker"] + "+OR+"
    if len(i_prefs) > 0:
        for i in i_prefs:
            q += i["name"] + "+OR+"
        q = q[:-3]


    # iteratively load user company and industry preferences into query for lookupArticles
    geo = ""
    if len(g_prefs) > 0:
        for i in g_prefs:
            geo += i["name"] + "OR"
        geo = geo[:-2]

    news = lookupArticles(geo=geo, q=q)
    return render_template("index.html", news=news)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure e-mail was submitted
        if not request.form.get("email"):
            flash("Must provide e-mail")
            return render_template("login.html")

        # ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return render_template("login.html")

        # query database for e-mail
        rows = db.execute("SELECT * FROM users WHERE email = :email", email=request.form.get("email"))
        
        # ensure e-mail exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            flash("Invalid e-mail and/or password")
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

        # ensure e-mail was submitted and that likely is valid
        if not request.form.get("email") or not verifyEmail(request.form.get("email")):
            flash("Must provide valid e-mail")
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

        # check email doesn't already exist
        repeated = db.execute("SELECT * FROM users WHERE email = :email", email=request.form.get("email"))
        if len(repeated) > 0:
            flash("E-mail is already taken!")
            return render_template("register.html")
            
        # query database for email
        rows = db.execute("INSERT INTO users (email, hash) VALUES (:email, :pwhash)", 
                                email=request.form.get("email"), 
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
            
            # check whether user follows company
            idCompany = db.execute("SELECT id FROM companies WHERE name = :name", name = stock["name"])

            # if company is not in database, add it and get id
            if len(idCompany) == 0:
                idCompany = db.execute("INSERT INTO companies (name, ticker) VALUES (:name, :ticker)", name = stock["name"], ticker = stock["symbol"])
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

            # check whether user follows industry
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

            return render_template("results.html", title="Industry: " + name, idGroup = idIndustry, category = "Industry", followed = followed, news = lookupArticles(q=request.form.get("prompt")))

        if request.form.get("button") == "geography":

            name = request.form.get("prompt").capitalize()

            # check whether user follows geography
            # get company id
            idGeography = db.execute("SELECT id FROM geographies WHERE name = :name", name = name)

            # if company is not in database, add it and get id
            if len(idGeography) == 0:
                idGeography = db.execute("INSERT INTO geographies (name) VALUES (:name)", name = name)
            else:
                idGeography = idGeography[0]["id"]

            # check if company is in user's interest
            rows = db.execute("SELECT * FROM userGeography WHERE idUser = :idUser AND idGeography = :idGeography", idUser = session["user_id"], idGeography = idGeography)

            if len(rows) == 0:
                followed = False
            else:
                followed = True

            return render_template("results.html", title="Geography: " + name, news = lookupArticles(geo=request.form.get("prompt")), category = "Geography", idGroup = idGeography, followed=followed)

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("search.html")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Change account settings"""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if request.form.get("btn") == "email":

            # ensure e-mail was submitted and is likely valid
            if not request.form.get("email") or not verifyEmail(request.form.get("email")):
                flash("E-mail required")
                return render_template("account.html")
            
            # update email
            db.execute("UPDATE users SET email = :email WHERE id = :id", email = request.form.get("email"), id = session["user_id"])
            flash("E-mail Changed!")

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

    category = request.args.get('category')
    if request.args.get('id') and request.args.get('follow') and request.args.get('category'):
        if request.args.get('follow') == "true":
            db.execute("INSERT INTO :userCat (idUser, :idCat) VALUES (:idUser, :id)", userCat = "user" + category, idCat = "id" + category, idUser = session["user_id"], id = request.args.get('id'))
            # print("INSERTED")
        else:
            deleteStr = "DELETE FROM {} WHERE idUser={} AND {}={}".format("user" + category, session["user_id"], "id" + category, request.args.get('id'))
            db.execute(deleteStr)
            # print("DELETED")
    return "update"
    
@app.route("/preferences")
@login_required
def preferences():
    """View/remove preferences."""

    userCompany = db.execute("SELECT idCompany, name FROM userCompany INNER JOIN companies ON idCompany = id WHERE idUser = :idUser ORDER BY name ASC", idUser = session["user_id"])
    userIndustry = db.execute("SELECT idIndustry, name FROM userIndustry INNER JOIN industries ON idIndustry = id WHERE idUser = :idUser ORDER BY name ASC", idUser = session["user_id"])
    userGeography = db.execute("SELECT idGeography, name FROM userGeography INNER JOIN geographies ON idGeography = id WHERE idUser = :idUser ORDER BY name ASC", idUser = session["user_id"])
    return render_template("preferences.html", userCompany = userCompany, userIndustry = userIndustry, userGeography = userGeography)

@app.route("/unfollow", methods=["POST"])
@login_required
def unfollow():
    """View/remove preferences."""

    if not request.form.get("Company") and not request.form.get("Industry") and not request.form.get("Geography"):
        flash("All fields required")
        return redirect(url_for("preferences"))
    current = []
    for i in request.form:
        current.append(i)
        current.append(request.form.get(i))
    deleteStr = "DELETE FROM {} WHERE idUser={} AND {}={}".format("user" + current[0], session["user_id"], "id" + current[0], current[1])
    db.execute(deleteStr)

    return redirect(url_for("preferences"))

@app.route("/about")
def about():
    """Render about."""

    return render_template("about.html")

@app.route("/contact")
def contact():
    """Render contact."""
    
    return render_template("contact.html")

def verifyEmail(email):
    """Verify e-mail formatting"""

    # check that e-mail matches expected formatting
    match = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
    if match == None:
        return False
    else:
        return True




