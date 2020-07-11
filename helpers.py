import os,requests

def goodreads(isbn):
    res = requests.get("https://www.goodreads.com/book/review_counts.json",{"key": "95mXpIWNa0rxr4sQXAg", "isbns": isbn})
    return res


def main():
    return "Empty"


if __name__ == "__main__":
    main()
