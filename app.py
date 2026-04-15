from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from exa_factcheck import FactVerifier


app = Flask(__name__)
load_dotenv()


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '')
app.config['SESSION_TYPE'] = 'filesystem'

db = SQLAlchemy(app)


try:
    fact_checker = FactVerifier(api_key=os.getenv('EXA_API_KEY'))
except:
    fact_checker = None
    print("ВНИМАНИЕ: API ключ не найден или недействителен")


class User(db.Model):
    username = db.Column(db.String(50), primary_key=True)
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
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Заполните все поля')
            return render_template('auto.html')

        if len(username) < 3 or len(username) > 50:
            flash('Имя пользователя должно быть от 3 до 50 символов')
            return render_template('auto.html')

        existing_user = User.query.get(username)
        if existing_user:
            flash('Пользователь с таким именем уже существует')
            return render_template('auto.html')

        try:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Регистрация успешна! Теперь вы можете войти')
            return redirect('/login')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при регистрации: {str(e)}')
            return render_template('auto.html')

    return render_template('auto.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Заполните все поля')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session.clear()
            session['username'] = username
            session.permanent = True
            session['logged_in'] = True
            return redirect('/dashboard')
        else:
            flash('Неверное имя пользователя или пароль')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        flash('Необходимо войти в систему')
        return redirect('/login')

    return render_template('dashboard.html', username=session.get('username'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы')
    return redirect(url_for('welcome'))


@app.route('/ai', methods=['GET', 'POST'])
def ai():
    if not session.get('logged_in'):
        flash('Для проверки фактов необходимо войти в систему')
        return redirect('/login')

    result = None
    error = None

    if request.method == "POST":
        text = request.form.get('title')

        if not text:
            flash('Введите текст для проверки')
        elif len(text) > 5000:
            flash('Текст слишком длинный (максимум 5000 символов)')
        else:
            try:
                if fact_checker:
                    verification_result = fact_checker.check(text)
                    result = verification_results(verification_result)
                else:
                    error = "Сервис проверки временно недоступен"
            except Exception as e:
                error = f"Ошибка при проверке: {str(e)}"

    return render_template('ai.html', result=result, error=error)


def verification_results(data):

    if not data or 'claims' not in data:
        return "Не удалось получить результаты проверки"

    lines = ["РЕЗУЛЬТАТЫ ПРОВЕРКИ"]

    for i, claim in enumerate(data['claims'], 1):
        lines.extend([
            f"\n{i}. Утверждение:",
            f"{claim['text']}",
            f"Оценка: {claim['verdict']}",
            f"Достоверность: {claim['confidence']}%"
        ])

        if claim.get('explanation'):
            lines.append(f"Пояснение: {claim['explanation']}")

        if claim.get('sources'):
            lines.append("Источники:")
            for src in claim['sources'][:3]:
                lines.append(f"{src}")

    return "\n".join(lines)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
