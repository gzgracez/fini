import csv
import feedparser
import urllib.parse
import urllib.request
import json

from flask import redirect, render_template, request, session, url_for
from functools import wraps
from bs4 import BeautifulSoup

def apology(top="", bottom=""):
    """Renders message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
            ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=escape(top), bottom=escape(bottom))

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def lookup(symbol):
    """Look up quote for symbol."""

    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None

    # reject symbol if it contains comma
    if "," in symbol:
        return None

    # query Yahoo for quote
    # http://stackoverflow.com/a/21351911
    try:
        url = "http://download.finance.yahoo.com/d/quotes.csv?f=snl1&s={}".format(symbol)
        webpage = urllib.request.urlopen(url)
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
        row = next(datareader)
    except:
        return None

    # ensure stock exists
    try:
        price = float(row[2])
    except:
        return None

    # return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
    return {
        "name": row[1],
        "price": price,
        "symbol": row[0].upper()
    }

def usd(value):
    """Formats value as USD."""
    return "${:,.2f}".format(value)
    
def transactions_display(shares, cash):
    total = cash
    for i in shares:
        info = lookup(i["symbol"])
        t = i["SUM(shares)"] * info["price"]
        i["total"] = usd(t)
        total += t
        i["price"] = usd(info["price"])
        i["name"] = info["name"]
    return [shares, usd(total)]

def lookupArticles(geo):
    """Looks up articles for geo."""

    # check cache for geo
    # if geo in lookup.cache:
    #     return lookup.cache[geo]

    # get feed from Google
    feed = feedparser.parse("http://news.google.com/news?geo={}&output=rss".format(urllib.parse.quote(geo, safe="")))

    # if no items in feed, get feed from Onion
    if not feed["items"]:
        feed = feedparser.parse("http://www.theonion.com/feeds/rss")


    news = []
    for i in feed["items"]:
        temp = {}
        # print(json.dumps(i, indent=4))
        temp["title"] = i.title
        temp["link"] = i.link
        # print(soup.prettify())
        try:
            value = i.summary_detail.value
            soup = BeautifulSoup(value, 'html.parser')
            b = soup.findAll("font", size="-1")
            temp["details"] = b[1].text
            print(b[1])
        except Exception as e:
            print(e)
            # return "Could not find food data."
        # return body
        news.append(temp)
    print(json.dumps(news, indent=4))
    return news
    # return [{"link": item["link"], "title": item["title"]} for item in feed["items"]]
    # return [{"link": item["link"], "title": item["title"]} for item in feed["items"]]




    # # return results
    # return lookup.cache[geo]

# # initialize cache
# lookup.cache = {}