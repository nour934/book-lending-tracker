from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import json
import os
from datetime import datetime, date
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

users = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"}
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_books():
    if os.path.exists('data.json'):
        with open('data.json', 'r') as f:
            return json.load(f)
    return []

def save_books(book_list):
    with open('data.json', 'w') as f:
        json.dump(book_list, f, indent=2)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in users and users[username]['password'] == password:
            session['role'] = users[username]['role']
            flash(f"Logged in as {username} ({session['role']})", 'info')
            if session['role'] == 'admin':
                return redirect(url_for('books'))
            else:
                return redirect(url_for('user'))
        flash('Invalid credentials', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/books', methods=['GET', 'POST'])
def books():
    if session.get('role') != 'admin':
        flash('Access denied: Admins only.', 'danger')
        return redirect(url_for('login'))

    book_list = load_books()
    query = request.args.get('q', '').strip().lower()
    genre_filter = request.args.get('genre', '').strip()

    if query:
        book_list = [book for book in book_list if query in book['title'].lower()]
    if genre_filter:
        book_list = [book for book in book_list if book.get('genre', '').lower() == genre_filter.lower()]

    today = str(date.today())
    for book in book_list:
        if book.get("status") == "Borrowed" and book.get("due_date") and not book.get("returned", True):
            if date.fromisoformat(book["due_date"]) < date.today():
                book["status"] = "Overdue"

    save_books(load_books())  # Save original data
    return render_template('books.html', books=book_list, now=today, role='admin')


@app.route('/user')
def user():
    if session.get('role') != 'user':
        flash('Access denied: Users only.', 'danger')
        return redirect(url_for('login'))

    book_list = load_books()
    query = request.args.get('q', '').strip().lower()
    genre_filter = request.args.get('genre', '').strip()

    if query:
        book_list = [book for book in book_list if query in book['title'].lower()]
    if genre_filter:
        book_list = [book for book in book_list if book.get('genre', '').lower() == genre_filter.lower()]

    today = str(date.today())
    for book in book_list:
        if book.get("status") == "Borrowed" and book.get("due_date") and not book.get("returned", True):
            if date.fromisoformat(book["due_date"]) < date.today():
                book["status"] = "Overdue"

    save_books(load_books())
    return render_template('user.html', books=book_list, now=today)

@app.route('/add', methods=['POST'])
def add_book():
    if session.get('role') != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('login'))

    book_list = load_books()
    title = request.form['title'].strip()
    genre = request.form.get('genre', '').strip()
    borrower = {
        "name": request.form.get('borrower_name', '').strip(),
        "phone": request.form.get('borrower_phone', '').strip(),
        "email": request.form.get('borrower_email', '').strip()
    }
    due_date = request.form.get('due_date', '')
    returned = request.form.get('returned') == 'Yes'
    status = "Available" if returned else "Borrowed"

    image = request.files.get('image')
    image_filename = ''
    if image and allowed_file(image.filename):
        image_filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

    new_book = {
        "title": title,
        "genre": genre,
        "status": status,
        "borrower": borrower,
        "due_date": due_date,
        "returned": returned,
        "image": image_filename
    }

    book_list.append(new_book)
    save_books(book_list)
    flash('Book added successfully!', 'success')
    return redirect(url_for('books'))

@app.route('/edit/<int:index>', methods=['GET', 'POST'])
def edit_book(index):
    if session.get('role') != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('login'))

    book_list = load_books()
    if index >= len(book_list):
        flash('Invalid book index.', 'warning')
        return redirect(url_for('books'))

    if request.method == 'POST':
        book = book_list[index]
        book['title'] = request.form['title']
        book['genre'] = request.form.get('genre', '').strip()
        book['borrower'] = {
            "name": request.form['borrower_name'],
            "phone": request.form['borrower_phone'],
            "email": request.form['borrower_email']
        }
        book['due_date'] = request.form['due_date']
        book['returned'] = request.form['returned'] == 'Yes'
        book['status'] = "Available" if book['returned'] else "Borrowed"

        image = request.files.get('image')
        if image and allowed_file(image.filename):
            image_filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            book['image'] = image_filename

        save_books(book_list)
        flash('Book updated successfully!', 'info')
        return redirect(url_for('books'))

    book = book_list[index]
    return render_template('edit.html', book=book, index=index)

@app.route('/delete/<int:index>', methods=['POST'])
def delete_book(index):
    if session.get('role') != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('login'))

    book_list = load_books()
    if 0 <= index < len(book_list):
        deleted = book_list.pop(index)
        save_books(book_list)
        flash(f"Deleted '{deleted['title']}'", 'danger')
    return redirect(url_for('books'))

@app.route('/download')
def download():
    return send_file('data.json', as_attachment=True)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render needs this
    app.run(host="0.0.0.0", port=port)
