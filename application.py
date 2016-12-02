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
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    cash = db.execute("SELECT cash FROM users WHERE id = :uid", uid=session["user_id"])[0]["cash"]
    shares = db.execute("SELECT SUM(shares), symbol FROM transactions WHERE user_id = :uid GROUP BY symbol HAVING SUM(shares) > 0", uid=session["user_id"])
    transactions = transactions_display(shares, cash)
    return render_template("index.html", total=transactions[1], cash=usd(cash), transactions=transactions[0])

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol")
            
        # ensure shares were submitted
        elif not request.form.get("shares"):
            return apology("missing shares")
            
        # ensure shares is a positive integer
        elif not request.form.get("shares").isdigit() or int(request.form.get("shares")) <= 0:
            return apology("invalid shares")
        info = lookup(request.form.get("symbol"))
        
        # ensure symbol is valid
        if not info:
            return apology("invalid symbol")
        cash = db.execute("SELECT cash FROM users WHERE id = :uid", uid=session["user_id"])[0]["cash"]
        price = float(info["price"]) * int(request.form.get("shares"))
        
        # ensure user has enough cash
        if (price > float(cash)):
            return apology("can't afford")
            
        # insert transaction
        transaction = db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:uid, :symbol, :shares, :sprice)", 
                                uid=session["user_id"], 
                                symbol=request.form.get("symbol").upper(),
                                shares=request.form.get("shares"),
                                sprice=info["price"]
                                )
                      
        newCash = cash-price          
        # update cash
        db.execute("UPDATE users SET cash = :new_cash WHERE id=:uid",
                    new_cash=newCash,
                    uid=session["user_id"])
                    
        shares = db.execute("SELECT SUM(shares), symbol FROM transactions WHERE user_id = :uid GROUP BY symbol HAVING SUM(shares) > 0", uid=session["user_id"])

        # get transactions to display
        transactions = transactions_display(shares, newCash)
        flash("Bought!")
        return render_template("index.html", total=transactions[1], cash=usd(newCash), transactions=transactions[0])
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    transactions = db.execute("SELECT timestamp, symbol, shares, price FROM transactions WHERE user_id = :uid ORDER BY timestamp ASC", uid=session["user_id"])
    for i in transactions:
        i["price"] = usd(i["price"])
    return render_template("history.html", transactions=transactions)

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

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol")
            
        # ensure shares were submitted
        elif not request.form.get("shares"):
            return apology("missing shares")

        # ensure shares is a positive integer
        elif not request.form.get("shares").isdigit() or int(request.form.get("shares")) <= 0:
            return apology("invalid shares")
            
        info = lookup(request.form.get("symbol"))
        
        # ensure symbol is valid
        if not info:
            return apology("invalid symbol")
            
        shares = db.execute("SELECT SUM(shares) FROM transactions WHERE user_id = :uid AND symbol = :symbol", 
                            uid=session["user_id"], 
                            symbol=request.form.get("symbol").upper())
        
        # ensure you own the stock
        if not shares[0]["SUM(shares)"]:
            return apology("symbol not owned")
        
        # ensure you have enough shares
        if int(request.form.get("shares")) > shares[0]["SUM(shares)"]:
            return apology("too many shares")
            
        # insert transaction
        transaction = db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:uid, :symbol, :shares, :sprice)", 
                                uid=session["user_id"], 
                                symbol=request.form.get("symbol").upper(),
                                shares=-1*int(request.form.get("shares")),
                                sprice=info["price"]
                                )
                      
        cash = db.execute("SELECT cash FROM users WHERE id = :uid", uid=session["user_id"])[0]["cash"]
        newCash = cash + (info["price"] * int(request.form.get("shares")))
        
        # update cash
        db.execute("UPDATE users SET cash = :new_cash WHERE id=:uid",
                    new_cash=newCash,
                    uid=session["user_id"])
                    
        allShares = db.execute("SELECT SUM(shares), symbol FROM transactions WHERE user_id = :uid GROUP BY symbol HAVING SUM(shares) > 0", uid=session["user_id"])

        # get transactions to display
        transactions = transactions_display(allShares, newCash)
        flash("Sold!")
        return render_template("index.html", total=transactions[1], cash=usd(newCash), transactions=transactions[0])
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    """Adds cash to account."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # ensure symbol was submitted
        if not request.form.get("cash"):
            return apology("missing amount to add")

        # ensure shares is valid positive dollar notation
        elif not re.match(r'\d+(?:[.]\d{2})?$', request.form.get("cash")) or float(request.form.get("cash")) <= 0:
            return apology("invalid amount")
            
        cash = db.execute("SELECT cash FROM users WHERE id = :uid", uid=session["user_id"])[0]["cash"]
        newCash = cash + float(request.form.get("cash"))
        
        # update cash
        db.execute("UPDATE users SET cash = :new_cash WHERE id=:uid",
                    new_cash=newCash,
                    uid=session["user_id"])

        allShares = db.execute("SELECT SUM(shares), symbol FROM transactions WHERE user_id = :uid GROUP BY symbol HAVING SUM(shares) > 0", uid=session["user_id"])

        # get transactions to display
        transactions = transactions_display(allShares, newCash)
        flash("Added cash!")
        return render_template("index.html", total=transactions[1], cash=usd(newCash), transactions=transactions[0])
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("addcash.html")

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
            return apology("You pressed", "industry")
        if request.form.get("button") == "geography":
            return apology("You pressed", "geography")
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("search.html")

@app.route("/articles")
def articles():
    """Look up articles for geo."""

    articles = lookup(request.args.get('geo'))
        
    return jsonify(articles)