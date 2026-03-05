from flask import Flask, render_template, url_for, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from exa_factcheck import ExaFactChecker


app = Flask(__name__)
load_dotenv()
fact_checker = ExaFactChecker()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'k17m12t12!'
db = SQLAlchemy(app)


class User(db.Model):
    login = db.Column(db.String(50), primary_key=True)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/auto', methods=['GET', 'POST'])
def auto():
    if request.method == "POST":
        login = request.form['login']
        password = request.form['password']

        existing_user = User.query.get(login)
        if existing_user:
            return "Пользователь с таким логином уже существует существует"

        user = User(login=login)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            return redirect('/login')
        except Exception as e:
            return f"Произошла ошибка: {str(e)}"

    return render_template('auto.html')


@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect('/login')

    return render_template('dashboard.html', login=session.get('username'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        login = request.form['login']
        password = request.form['password']

        user = User.query.get(login)

        if user and user.check_password(password):
            session['login'] = login
            session['logged_in'] = True
            return redirect('/dashboard')
        else:
            return render_template('login.html', error="Неверный логин или пароль")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('welcome'))


@app.route('/ai', methods=['GET', 'POST'])
def ai():
    result = None

    text_check = request.form.get('title', '')
    if text_check:
        try:
            verify_result = fact_checker.fact_check(text_check)

            if verify_result:
                result = format_results(verify_result)

            else:
                result = "Не удалось проверить текст"

        except Exception as e:
            result = f"Ошибка при проверке: {str(e)}"

    return render_template('ai.html', result=result)


def format_results(results):
    formatted = "РЕЗУЛЬТАТЫ ПРОВЕРКИ ФАКТОВ:\n"

    for i, res in enumerate(results, 1):
        formatted += f"Утверждение {i}: {res['claim']}\n"
        formatted += f"Оценка: {res['assessment']}\n"
        formatted += f"Уверенность: {res['confidence']}%\n"

        if res.get('explanation'):
            formatted += f"Пояснение: {res['explanation']}\n"

        if res.get('scientific_sources'):
            formatted += "\nНАУЧНЫЕ ИСТОЧНИКИ:\n"
            for src in res['scientific_sources']:
                formatted += f"  • {src}\n"

        if not res.get('scientific_sources') and not res.get('pseudoscience_sources'):
            formatted += "\nНе найдены источники\n"

    return formatted


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
