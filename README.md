[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-lightgrey)](https://flask.palletsprojects.com/)

# Fact Checker — проверка фактов за секунду

Сервис для быстрой проверки новостей на достоверность.

## Возможности
- Регистрация и вход пользователей
- Проверка фактов с помощью ИИ (или демо-режим)
- Лимит 5 бесплатных проверок в день
- Премиум-подписка (безлимит)
- История всех проверок
- Темная тема

## Технологии
- Python + Flask
- SQLite (база данных)
- HTML, CSS (адаптивный дизайн)
- GitHub (контроль версий)

## Файлы, которые игнорируются
- `__pycache__/` — кеш Python
- `database.db` — локальная база данных
- `.env` — секретные ключи

## Быстрый старт

1. Клонируйте репозиторий:

```bash
git clone https://github.com/Tunev42/Fact_Checker.git
cd Fact_Checker
```

2. Установите зависимости:

```bash
pip install flask flask-sqlalchemy werkzeug python-dotenv
```

3. Запустите приложение:

```bash
python app.py
```

4. Откройте в браузере: http://127.0.0.1:5000

## Главная страница Fact Checker
![Главная страница](screenshot.png)
