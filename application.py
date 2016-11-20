from sql import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

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
    
    # query user's holdings
    holdings = db.execute("SELECT * FROM holdings WHERE users_id = :users_id", users_id = session["user_id"])
    
    # initiate total
    total = 0
    
    # iterate through holdings
    for holding in holdings:
        
        # retrieve updated prices (and put a name in there too)
        stock = lookup(holding["symbol"])
        
        holding["name"] = stock["name"]
        holding["price"] = usd(stock["price"])
        holding["total"] = usd(holding["shares"] * stock["price"])
        
        total += stock["price"] * holding["shares"]
    
    # query user's cash
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
    
    # add cash to total and format
    total = usd(total + float(cash))
    
    # format cash
    cash = usd(cash)
    
    return render_template("index.html", holdings = holdings, cash = cash, total = total)
    

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # store form input for convenience
        shares = request.form.get("shares")
        symbol = request.form.get("symbol")
        
        # ensure shares was submitted
        if not shares:
            return apology("must provide", "number of shares")

        # ensure symbol was submitted
        elif not symbol:
            return apology("must provide symbol")
        
        shares = float(shares)
        
        # retrieve stock name, price, symbol
        stock = lookup(symbol)
        
        if stock == None:
            return apology("invalid symbol")

        # retrieve users cash
        cash = float(db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"])
        
        # check liquidity
        if cash < stock["price"] * shares:
            return apology("insufficient liquidity")
            
        # update buyers cash
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash - stock["price"] * shares, id = session["user_id"])
            
        # update transaction log
        db.execute("INSERT INTO log (users_id, symbol, shares, price) VALUES (:users_id, :symbol, :shares, :price)",
            users_id = session["user_id"], symbol = stock["symbol"], shares = int(shares), price = stock["price"])
            
        # query for holding
        holding = db.execute("SELECT * FROM holdings WHERE users_id = :users_id AND symbol = :symbol",
                        users_id = session["user_id"], symbol = stock["symbol"])
        
        # if no holding excists, make it
        if len(holding) == 0:
            db.execute("INSERT INTO holdings (users_id, symbol, shares) VALUES (:users_id, :symbol, :shares)",
                users_id = session["user_id"], symbol = stock["symbol"], shares = int(shares))
        # otherwise, change shares
        else:
            db.execute("UPDATE holdings SET shares = :shares WHERE id = :id",
                shares = holding[0]["shares"] + int(shares), id = holding[0]["id"])
    
        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    history = db.execute("SELECT * FROM log")
    return render_template("history.html", history = history)

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
        
        # ensure ticker was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol")
        
        stock = lookup(request.form.get("symbol"))
        
        if stock == None:
            return apology("symbol not found")
        
        stock["price"] = usd(stock["price"])
        
        return render_template("quoted.html", stock = stock)
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")
            
        # query database for username
        rows = db.execute("SELECT username FROM users WHERE username = :username", username=request.form.get("username"))
        
        # if username already excists, deny registering that username
        if len(rows) > 0:
            return apology("username not available")

        # ensure password was submitted
        elif not request.form.get("password1"):
            return apology("must provide password")
        
        # ensure passwords match
        elif request.form.get("password2") != request.form.get("password1"):
            return apology("passwords must match")
            
        # insert user into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashed)",
            username = request.form.get("username"), hashed = pwd_context.encrypt(request.form.get("password1")))
        
        # return to login window
        return render_template("login.html")
            
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # store form input for convenience
        sale = request.form.get("shares")
        symbol = request.form.get("symbol")
        
        # ensure shares was submitted
        if not sale:
            return apology("must provide", "number of shares")

        # ensure symbol was submitted
        elif not symbol:
            return apology("must provide symbol")
            
        sale = float(sale)
        
        # retrieve stock name, price, symbol
        stock = lookup(symbol)
        
        if stock == None:
            return apology("invalid symbol")
        
        # retrieve users holding
        holding = db.execute("SELECT id, shares FROM holdings WHERE users_id = :users_id AND symbol = :symbol",
                        users_id = session["user_id"], symbol = stock["symbol"])
        
        # check user owns sufficient shares
        if len(holding) == 0 or int(holding[0]["shares"]) < sale:
            return apology("insufficient holdings")
            
        # store id and shares
        id = holding[0]["id"]
        shares = int(holding[0]["shares"])
        
        # update buyers cash
        cash = float(db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"])
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash + stock["price"] * sale, id = session["user_id"])
        
        # update user's holding
        if shares == sale:
            db.execute("DELETE FROM holdings WHERE id = :id", id = id)
        else:
            db.execute("UPDATE holdings SET shares = :shares WHERE id = :id",
                shares = shares - sale, id = id)
        
        # update transaction log
        db.execute("INSERT INTO log (users_id, symbol, shares, price) VALUES (:users_id, :symbol, :shares, :price)",
            users_id = session["user_id"], symbol = stock["symbol"], shares = int(-sale), price = stock["price"])

        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")
        
@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change password."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

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
        return render_template("password.html")
            
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("password.html")