from sql import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
import re

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

# custom filter
app.jinja_env.filters["usd"] = usd

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
    cash = db.execute("SELECT cash FROM users WHERE id = :uid", uid=session["user_id"])[0]["cash"]
    shares = db.execute("SELECT SUM(shares), symbol FROM transactions WHERE user_id = :uid GROUP BY symbol HAVING SUM(shares) > 0", uid=session["user_id"])
    transactions = transactions_display(shares, cash)
    news = lookupArticles("02138")
    return render_template("index.html", total=transactions[1], cash=usd(cash), transactions=transactions[0], news=news)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        
        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

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

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol")
        info = lookup(request.form.get("symbol"))
        if not info:
            return apology("invalid symbol")
        return render_template("quoted.html", name=info["name"], price=usd(info["price"]), symbol=info["symbol"])
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
            
        # ensure password was confirmed
        elif not request.form.get("confirmation"):
            return apology("must confirm password")
            
        # ensure confirmed password is the same
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("confirmed password does not match")

        # check username doesn't already exist
        repeated = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(repeated) > 0:
            return apology("username is already taken")
            
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
            return apology("No prompt", "input")

        # redirect based on button
        if request.form.get("button") == "company":
            return apology("You pressed", "company")
        if request.form.get("button") == "industry":
            return render_template("results.html", news = lookupArticles(geo="02138", q=request.form.get("prompt")))
        if request.form.get("button") == "geography":
            return render_template("results.html", news = lookupArticles(geo=request.form.get("prompt"), q=""))

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
                return apology("Grazzzzze required")
            
            # update username
            db.execute("UPDATE users SET username = :username WHERE id = :id", username = request.form.get("username"), id = session["user_id"])

        if request.form.get("btn") == "password":

            # ensure all fields were filled
            if not request.form.get("old") or not request.form.get("new") or not request.form.get("newr"):
                return apology("all fields required")
                
            old = request.form.get("old")
            new = request.form.get("new")
            newr = request.form.get("newr")
                
            # check old password
            if not pwd_context.verify(request.form.get("old"), db.execute("SELECT hash FROM users WHERE id = :id",
                id = session["user_id"])[0]["hash"]):
                    return apology("incorrect old password")
                
            # check that new passwords match
            elif new != newr:
                return apology("new passwords do not match")
            
            # update password
            db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash = pwd_context.encrypt(new), id = session["user_id"])
            
        # return to password window
        return render_template("account.html")
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("account.html")

@app.route("/articles")
def articles():
    """Look up articles for geo."""

    articles = lookup("request.args.get('geo')")
    
    return jsonify(articles)

@app.route("/results_comp", methods=["GET", "POST"])
@login_required
def results_comp():
    """Search for company, industry or geography"""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        return apology("TODO")
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("results_comp.html")