import os, json

from flask import Flask, session, render_template, request, jsonify, flash, url_for, redirect
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from werkzeug.security import check_password_hash, generate_password_hash
from helpers import goodreads

import requests

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    if session.get("logged_in"):
        return render_template("search.html")

    else:
        return render_template("welcome.html")


#when login request
@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()
    username = request.form.get("username")

    if request.method == "POST":

        if not request.form.get("username"):
            return render_template("error.html",message="Please Enter your Username")
        elif not request.form.get("password"):
            return render_template("error.html",message="Please Enter your Password")

        res = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()

        if res == None or not check_password_hash(res[1], request.form.get("password")):
            return render_template("error.html", message="An invalid username or password, Please retry")

        session["user_name"] = username
        session["logged_in"] = True

        flash("Welcome.")
        return redirect("/")

    else:
        return render_template("welcome.html")

#when search request
@app.route("/search", methods=["GET"])
def search():
    if session.get("logged_in"):

        if not request.args.get("search"):
            return render_template("error.html", message="Enter a book title or author name.")

        book = "%" + request.args.get("search") + "%"

        book = book.title()

        rows=db.execute("SELECT * FROM books WHERE (title LIKE :book) OR (author LIKE :book) OR (isbn LIKE :book)", {"book": book})

        if rows.rowcount == 0:
            return render_template("error.html", message="No books were found!")

        books = rows.fetchall()

        return render_template("books.html", books=books)

    else:
        return render_template("welcome.html")

#when logout request
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

#When user ask for registration
@app.route("/register", methods=["POST" , "GET"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username:
            return render_template("error.html", message="Please give a username.")
        if not password:
            return render_template("error.html", message="Please give a password.")
        row = db.execute("SELECT * FROM users WHERE username= :username", {"username": username})
        if(row.rowcount > 0):
            return render_template("error.html", message="username is already exist.Please try another")
        else:
            hPassword = generate_password_hash(request.form.get("password"), method= "pbkdf2:sha256", salt_length =8)
            db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username" :username, "password" :hPassword})
            db.commit()
            session["user_name"] = username
            session["logged_in"] = True
            return redirect("/")
    else:
        return render_template("register.html")

@app.route("/book/<isbn>" , methods=["Post" , "GET"])
def book(isbn):
    if request.method == "POST":
        sessionuser = session["user_name"]
        rating = int(request.form.get("rating"))
        comment = request.form.get("comment")

        rows = db.execute("SELECT isbn FROM books WHERE isbn = :isbn", {"isbn" :isbn})
        bookisbn = rows.fetchone()
        bookisbn = bookisbn[0]

        res = db.execute("SELECT * FROM reviews WHERE username = :username AND bookisbn = :bookisbn", {"username":sessionuser , "bookisbn" :bookisbn})
        if res.rowcount > 0:
            return render_template("error.html", message="Your review already has been recorded for this book")

        db.execute("INSERT INTO reviews (username,bookisbn,comment,rating) VALUES (:username,:bookisbn,:comment,:rating)",{"username" :sessionuser, "bookisbn" :bookisbn , "comment" :comment, "rating" :rating})
        db.commit()
        return render_template("error.html", message="Thank You!")
        return redirect("/book/"+isbn)
    else:
        rows = db.execute("SELECT isbn,author, year, title FROM books WHERE isbn = :isbn", {"isbn" :isbn})
        bookinfo = rows.fetchall()

        resp = goodreads(isbn)
        resp = resp.json()
        resp = resp['books'][0]

        bookinfo.append(resp)

        row = db.execute("SELECT isbn FROM books WHERE isbn = :isbn" , {"isbn" :isbn})
        row = row.fetchone()
        bookisbn = row[0]

        res = db.execute("SELECT users.username , bookisbn, comment, rating FROM users INNER JOIN reviews ON users.username = reviews.username WHERE bookisbn = :bookisbn", {"bookisbn" :bookisbn})
        reviews = res.fetchall()

        return render_template("review.html", bookinfo=bookinfo,reviews=reviews)


@app.route("/api/<isbn>", methods=["GET"])
def api(isbn):
    bookApi = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()

    if bookApi is None:
        goodreads = get_goodreads(isbn)
        if goodreads.status_code != 200:
            return abort(404)
        else:
            bookApi = goodreads.json()
            return bookApi
    else:
        book_reviews = db.execute("SELECT COUNT(username), AVG(rating) FROM reviews WHERE bookisbn = :bookisbn",{"bookisbn": bookApi.isbn},).fetchone()

    res = {}
    res["title"] = bookApi.title
    res["author"] = bookApi.author
    res["year"] = bookApi.year
    res["isbn"] = bookApi.isbn
    try:
        res["review_count"] = str(book_reviews[0])
        res["average_score"] = "% 1.1f" % book_reviews[1]
    except TypeError:
        res["review_count"] = "Not enough reviews"
        res["average_score"] = "Not enough reviews"

    json_res = json.dumps(res)

    return json_res, 200
