import csv
import feedparser
import urllib.parse
import urllib.request
import json
import cssselect

from urllib.parse import urlencode, urlparse, parse_qs
from lxml.html import fromstring
from requests import get
import requests
from flask import redirect, render_template, request, session, url_for
from functools import wraps
from bs4 import BeautifulSoup

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
    """Look up stock by Yahoo Finance."""

    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None

    # reject symbol if it contains comma
    if "," in symbol:
        return None

    if not symbol.isalpha():
        return None

    # query Yahoo for stock data
    # http://stackoverflow.com/a/21351911
    try:
        url = "http://download.finance.yahoo.com/d/quotes.csv?f=snl1mvj1re7&s={}".format(symbol)
        webpage = urllib.request.urlopen(url)
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
        row = next(datareader)
    except:
        return None

    # ensure stock exists, and format
    try:
        price = usd(float(row[2]))
    except:
        return None

    # format range
    try: 
        ranges = row[3].split(' - ')
        range_low = usd(float(ranges[0]))
        range_high = usd(float(ranges[1]))
    except:
        range_low = ""
        range_high =""

    # format volume
    try:
        volume = thousands(int(row[4]))
    except:
        volume = "-"

    # get stock icon
    icon = getIconUrl(symbol)

    # return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
    return {
        "name": row[1],
        "price": price,
        "symbol": row[0].upper(),
        "range_low": range_low,
        "range_high": range_high,
        "volume": volume,
        "mcap": row[5],
        "peratio": row[6],
        "eps": row[7],
        "icon": icon
    }

def usd(value):
    """Formats value as USD."""
    return "${:,.2f}".format(value)

def thousands(value):
    """Comma-seperates thousands."""
    return "{0:,}".format(value)

def getIconUrl(symbol):
    """Return stock icon url."""
    if symbol in logoCache:
        return logoCache[symbol]
    url = "http://www.google.com/search?q=ticker+" + symbol
    website = requests.get(url)
    if website.status_code != 200: 
        logoCache[symbol] = None
        return None
    soup = BeautifulSoup(website.content)
    try:
        img = soup.findAll('img', {'style': 'margin-left:0px;margin-right:0px'})[0]['src']
        logoCache[symbol] = img
    except Exception as e:
        print(e)
        logoCache[symbol] = None
    return logoCache[symbol]

def lookupArticles(geo="", q="", topic=""):
    """Looks up articles for geo, q and topic."""

    # feed = feedparser.parse("http://news.google.com/news?geo={}&q={}&output=rss".format(urllib.parse.quote(geo, safe=""), urllib.parse.quote(q, safe="")))
    feed = feedparser.parse("http://news.google.com/news?geo={}&q={}&topic={}&output=rss".format(geo, q, topic))

    # if no items in feed, get default business feed
    if not feed["items"]:
        feed = feedparser.parse("http://news.google.com/news?topic=b&output=rss")
    news = []
    for i in feed["items"]:
        temp = {}
        temp["title"] = i.title
        temp["link"] = i.link
        try:
            value = i.summary_detail.value
            soup = BeautifulSoup(value, 'html.parser')
            detail = soup.findAll("font", size="-1")
            temp["details"] = detail[1].text
            temp["imgurl"] = soup.findAll("img")[0]['src']
        except Exception as e:
            print(e)
            # return "Could not find food data."
        news.append(temp)
    return news

# initialize cache
logoCache = {}