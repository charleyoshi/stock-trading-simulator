import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from tkinter import messagebox


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute(
        "SELECT symbol,stock_name, SUM(shares) as total_shares FROM history where user_id = ? GROUP BY symbol HAVING total_shares > 0", session["user_id"])
    
    # print('--------------------')
    # print(rows)
    
    total = 0
    holdings = [] # a list of dictionaries of holding stocks
    for row in rows:
        quote = lookup(row['symbol'])
        holdings.append({
            'symbol': row['symbol'],
            'name': quote['name'],
            'shares': row['total_shares'],
            'price': usd(quote['price']),
            'total': usd(row['total_shares'] * quote['price'])
        })
        total += row['total_shares'] * quote['price']
        
        
    cash_balance = float(db.execute('SELECT cash FROM users where id = ?', session["user_id"])[0]['cash'])
    total += cash_balance
    return render_template("index.html", holdings=holdings, cash_balance=usd(cash_balance), total=usd(total))
    

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        # display a form to request a stock quote
        return render_template('buy.html')
        
    else:  # if request.method == "POST"
        # lookup the stock symbol (AAPL) by calling the lookup function, and display the results
        symbol = request.form.get('symbol').upper()
        shares = request.form.get('shares')
        if not symbol:
            return apology('Missing symbol', 400)
            
        if not shares:
            return apology('Missing shares', 400)

        # shares=int(request.form.get('shares'))
        if not shares.isdigit():
            return apology('Only accepts positive integers', 400)
        
        shares = int(request.form.get('shares'))
        quote = lookup(symbol)
        if not quote:
            return apology('Not in the stock list', 400)
        
        stock_name = quote['name']
        stock_price = quote['price']
        total = stock_price * shares
        
        cash = db.execute("SELECT cash FROM users where id = ?", session["user_id"])
        
        user_id = int(session["user_id"])
        cash = cash[0]['cash']
        if (total > cash):
            return render_template('buy_failure.html', shares=shares, stock_name=stock_name, total=usd(total), cash=usd(cash))
        
        db.execute(
            """INSERT INTO history (user_id, symbol,stock_name, shares, transacted_price) VALUES (?, ?, ?, ?, ?)""", user_id, symbol, stock_name, shares, quote['price'])
        
        cash = cash - total
        
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
        flash("Bought!")
        
        try:
            shares = int(request.form.get('shares'))
        except ValueError:
            return apology("shares must be positive integer", 400)
        
        return redirect('/')

        
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute(
        "SELECT symbol, shares, transacted_price, transacted FROM history where user_id = ? ORDER BY transacted", session["user_id"])
    holdings = []
    for row in rows:
        holdings.append({
            'symbol': row['symbol'], 
            'shares': row['shares'],
            'price': usd(row['transacted_price']),
            'transacted': row['transacted']
        })
    return render_template('history.html', holdings=holdings)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology('Provide username', 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology('Provide password', 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username").lower())

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template('login_failure.html')

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        
        username = request.form.get("username")
        # Redirect user to home page
        flash('Welcome back, ' + username + '! What\'s your pitch today?')
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        # display a form to request a stock quote
        return render_template('quote.html')
        
    else:  # if request.method == "POST"
        # lookup the stock symbol (AAPL) by calling the lookup function, and display the results
        
        symbol = request.form.get('symbol').upper()
        quote = lookup(symbol)
        if not symbol:
            return apology('Provide symbol', 400)
            
        if not quote:
            return apology('Not in the stock list', 400)
        stock_name = quote['name']
        stock_price = quote['price']
        
        return render_template('quote_result.html', stock_name=stock_name, symbol=symbol, stock_price=stock_price)
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template('/register.html')
        # display registration form
    
    else:  # (request.method == "POST")
        username = request.form.get('username').lower()  # username is all lowercase
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')
        #    insert the new user into users table (be sure to check for invalid inputs, and to hash the user's password)
        # 1. sorry username already taken/ 2. sorry passwords didn't match
        if not request.form.get("username"):
            return apology('Please provide username', 400)
            
        row = db.execute("SELECT * FROM users WHERE username = ?", username)
        
        if len(row) > 0:
            return apology('Username already taken', 400)


        if not request.form.get("confirmation"):
            return apology('Confirm your password', 400)

        if (password != confirmation):
            return apology('Passwords didn\'t match', 400)

        session.clear()
        password_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password_hash)
        row = db.execute("SELECT * FROM users WHERE username = ?", username)
        # SELECT * FROM users;  
        # DELETE FROM users WHERE id < 8;
        flash("You are registered as " + username + '! Try login now and then can start trading.  You have USD$10000 initially.')
        return render_template('login.html')
        

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    holdings = db.execute(
        "SELECT symbol,stock_name, SUM(shares) as total_shares FROM history where user_id = ? GROUP BY symbol HAVING total_shares > 0", session["user_id"])
    # holdings == [{'symbol': 'AAPL', 'name': 'Apple Inc', 'shares': 12, 'price': '$130.15', 'total': '$1,561.80'},
    #             {'symbol': 'NFLX', 'name': 'NetFlix Inc', 'shares': 5, 'price': '$492.41', 'total': '$2,462.05'}]    
    
    if request.method == "GET":
        return render_template('sell.html', holdings=holdings)
    
    else:  # if request.method == "POST"
        symbol = request.form.get('symbol')
        shares = request.form.get('shares')
        if not symbol:
            return apology('Missing symbol', 400)
        if not shares:
            return apology('Missing shares', 400)

        for holding in holdings:
            if (holding['symbol'] == symbol):
                if (holding['total_shares'] < int(shares)):
                    return apology('Not enough shares to sell', 400)

        user_id = int(session["user_id"])
        quote = lookup(symbol)
        
        db.execute(
            """INSERT INTO history (user_id, symbol, stock_name, shares, transacted_price) VALUES (?, ?, ?, ?, ?)""", user_id, symbol, quote['name'], (int(shares) * (-1)), quote['price'])        
        
        cash = db.execute(
            "SELECT cash FROM users where id = ?", session["user_id"])[0]['cash'] + quote['price']*int(shares)
        
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
        
        flash("Sold!")
        return redirect('/')


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    if request.method == "GET":
        return render_template('add_cash.html')
    else:  # request.method == "POST"
        add_cash = float(request.form.get('add_cash'))
        user_id = int(session["user_id"])
        cash = db.execute(
            "SELECT cash FROM users where id = ?", session["user_id"])[0]['cash']
        
        cash += add_cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
        flash("Added $" + str(add_cash) + '!')
        return redirect('/')
    
    
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


# CREATE TABLE history (transaction_ref INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, symbol TEXT NOT NULL, stock_name TEXT NOT NULL, shares INTEGER NOT NULL,transacted_price NUMERIC NOT NULL, transacted TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL);
# export API_KEY=pk_f2347b76a69d4ec0b404b5f9775b5806