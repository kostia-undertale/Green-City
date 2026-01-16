from flask import render_template, request, redirect, url_for, flash, session, jsonify
import database


def init_auth_routes(app):
    """Инициализация маршрутов аутентификации"""

    def admin_required(f):
        """Декоратор для проверки прав администратора или создателя"""
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Пожалуйста, войдите в систему', 'warning')
                return redirect(url_for('login'))
            if session.get('role') not in ['admin', 'creator']:
                flash('Доступ запрещен. Требуются права администратора', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)

        return decorated_function

    def creator_required(f):
        """Декоратор для проверки прав создателя"""
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Пожалуйста, войдите в систему', 'warning')
                return redirect(url_for('login'))
            if session.get('role') != 'creator':
                flash('Доступ запрещен. Требуются права создателя', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)

        return decorated_function

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            city = request.form['city']

            conn = database.get_db_connection()

            # Проверяем, существует ли пользователь с таким username или email
            existing_user = conn.execute(
                'SELECT id FROM users WHERE username = ? OR email = ?',
                (username, email)
            ).fetchone()

            if existing_user:
                flash('Пользователь с таким именем или email уже существует', 'danger')
                conn.close()
                cities_by_region = database.get_cities_by_region()
                return render_template('register.html', cities_by_region=cities_by_region)

            # Создаем пользователя
            password_hash = database.hash_password(password)
            conn.execute(
                'INSERT INTO users (username, email, password_hash, city) VALUES (?, ?, ?, ?)',
                (username, email, password_hash, city)
            )
            conn.commit()
            conn.close()

            flash('Регистрация успешна! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))

        cities_by_region = database.get_cities_by_region()
        return render_template('register.html', cities_by_region=cities_by_region)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            conn = database.get_db_connection()
            user = conn.execute(
                'SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)
            ).fetchone()
            conn.close()

            if user and database.verify_password(password, user['password_hash']):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['city'] = user['city']
                session['role'] = user['role']

                role_message = ""
                if user['role'] == 'admin':
                    role_message = " (администратор)"
                elif user['role'] == 'creator':
                    role_message = " (создатель)"

                flash(f'Добро пожаловать, {user["username"]}{role_message}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Неверное имя пользователя или пароль', 'danger')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('index'))

    @app.route('/profile')
    def profile():
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))

        conn = database.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        # Статистика пользователя
        user_stats = {
            'zones_added':
                conn.execute('SELECT COUNT(*) FROM green_zones WHERE created_by = ?', (session['user_id'],)).fetchone()[
                    0],
            'reports_submitted': conn.execute('SELECT COUNT(*) FROM zone_reports WHERE reporter_id = ?',
                                              (session['user_id'],)).fetchone()[0],
            'tasks_created': conn.execute('SELECT COUNT(*) FROM maintenance_tasks WHERE created_by = ?',
                                          (session['user_id'],)).fetchone()[0]
        }

        cities_by_region = database.get_cities_by_region()
        conn.close()

        return render_template('profile.html', user=user, stats=user_stats,
                               cities_by_region=cities_by_region, is_own_profile=True)

    @app.route('/change_city', methods=['POST'])
    def change_city():
        """Смена города пользователя"""
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))

        new_city = request.form['new_city']

        if not new_city:
            flash('Пожалуйста, выберите город', 'danger')
            return redirect(url_for('profile'))

        conn = database.get_db_connection()

        # Проверяем, что город существует в базе
        city_exists = conn.execute('SELECT id FROM cities WHERE name = ?', (new_city,)).fetchone()
        if not city_exists:
            flash('Выбранный город не найден в системе', 'danger')
            conn.close()
            return redirect(url_for('profile'))

        # Обновляем город пользователя
        conn.execute(
            'UPDATE users SET city = ? WHERE id = ?',
            (new_city, session['user_id'])
        )
        conn.commit()
        conn.close()

        # Обновляем город в сессии
        session['city'] = new_city

        flash(f'Город успешно изменен на {new_city}', 'success')
        return redirect(url_for('profile'))

    @app.route('/profile/<int:user_id>')
    def view_profile(user_id):
        """Просмотр профиля другого пользователя"""
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))

        # Администраторы и создатели могут смотреть чужие профили
        if session.get('role') not in ['admin', 'creator'] and session['user_id'] != user_id:
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('index'))

        conn = database.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

        if not user:
            flash('Пользователь не найден', 'danger')
            conn.close()
            return redirect(url_for('index'))

        # Статистика пользователя
        user_stats = {
            'zones_added': conn.execute('SELECT COUNT(*) FROM green_zones WHERE created_by = ?', (user_id,)).fetchone()[
                0],
            'reports_submitted':
                conn.execute('SELECT COUNT(*) FROM zone_reports WHERE reporter_id = ?', (user_id,)).fetchone()[0],
            'tasks_created':
                conn.execute('SELECT COUNT(*) FROM maintenance_tasks WHERE created_by = ?', (user_id,)).fetchone()[0]
        }

        cities_by_region = database.get_cities_by_region()
        conn.close()

        return render_template('profile.html', user=user, stats=user_stats,
                               is_own_profile=(session['user_id'] == user_id),
                               cities_by_region=cities_by_region)

    @app.route('/admin/users')
    @admin_required
    def admin_users():
        """Админ-панель: управление пользователями"""
        users = database.get_all_users()
        return render_template('admin_users.html', users=users)

    @app.route('/admin/cities')
    @admin_required
    def admin_cities():
        """Админ-панель: управление городами"""
        cities = database.get_all_cities()

        # Статистика для отображения
        regions = set(city['region'] for city in cities)
        total_population = sum(city['population'] or 0 for city in cities)
        cities_with_population = sum(1 for city in cities if city['population'])

        return render_template('admin_cities.html',
                               cities=cities,
                               regions=regions,
                               total_population=total_population,
                               cities_with_population=cities_with_population)

    @app.route('/admin/cities/search')
    @admin_required
    def search_cities():
        """Поиск городов (API endpoint)"""
        query = request.args.get('q', '').lower().strip()

        conn = database.get_db_connection()
        if query:
            cities = conn.execute('''
                    SELECT * FROM cities 
                    WHERE LOWER(name) LIKE ? OR LOWER(region) LIKE ?
                    ORDER BY name
                ''', (f'%{query}%', f'%{query}%')).fetchall()
        else:
            cities = conn.execute('SELECT * FROM cities ORDER BY name').fetchall()

        conn.close()

        # Преобразуем в JSON-совместимый формат
        cities_list = []
        for city in cities:
            cities_list.append({
                'id': city['id'],
                'name': city['name'],
                'region': city['region'],
                'population': city['population'],
                'created_date': city['created_date']
            })

        return jsonify(cities_list)

    @app.route('/admin/cities/add', methods=['POST'])
    @admin_required
    def add_city():
        """Добавление нового города"""
        name = request.form['name']
        region = request.form['region']
        population = request.form.get('population')

        if not name or not region:
            flash('Название города и регион обязательны для заполнения', 'danger')
            return redirect(url_for('admin_cities'))

        # Проверяем, существует ли уже такой город
        conn = database.get_db_connection()
        existing_city = conn.execute(
            'SELECT id FROM cities WHERE name = ?', (name,)
        ).fetchone()

        if existing_city:
            flash(f'Город "{name}" уже существует в системе', 'danger')
            conn.close()
            return redirect(url_for('admin_cities'))

        # Добавляем город
        try:
            population_int = int(population) if population else None
            conn.execute(
                'INSERT INTO cities (name, region, population) VALUES (?, ?, ?)',
                (name, region, population_int)
            )
            conn.commit()
            flash(f'Город "{name}" успешно добавлен', 'success')
        except Exception as e:
            flash('Ошибка при добавлении города', 'danger')
            print(f"Error adding city: {e}")
        finally:
            conn.close()

        return redirect(url_for('admin_cities'))

    @app.route('/admin/cities/<int:city_id>/delete', methods=['POST'])
    @admin_required
    def delete_city(city_id):
        """Удаление города"""
        conn = database.get_db_connection()

        # Проверяем существование города
        city = conn.execute('SELECT * FROM cities WHERE id = ?', (city_id,)).fetchone()
        if not city:
            flash('Город не найден', 'danger')
            conn.close()
            return redirect(url_for('admin_cities'))

        # Проверяем, есть ли пользователи с этим городом
        users_with_city = conn.execute(
            'SELECT COUNT(*) FROM users WHERE city = ?', (city['name'],)
        ).fetchone()[0]

        # Проверяем, есть ли зоны в этом городе
        zones_in_city = conn.execute(
            'SELECT COUNT(*) FROM green_zones WHERE city_id = ?', (city_id,)
        ).fetchone()[0]

        if users_with_city > 0:
            flash(f'Нельзя удалить город "{city["name"]}". Есть пользователи с этим городом.', 'danger')
            conn.close()
            return redirect(url_for('admin_cities'))

        try:
            # Удаляем город
            conn.execute('DELETE FROM cities WHERE id = ?', (city_id,))
            conn.commit()
            flash(f'Город "{city["name"]}" успешно удален', 'success')
        except Exception as e:
            flash('Ошибка при удалении города', 'danger')
            print(f"Error deleting city: {e}")
        finally:
            conn.close()

        return redirect(url_for('admin_cities'))

    @app.route('/admin/admins')
    @creator_required
    def admin_admins():
        """Панель создателя: управление администраторами"""
        admins = database.get_admins()
        return render_template('admin_admins.html', admins=admins)

    @app.route('/admin/users/<int:user_id>/toggle_role')
    @admin_required
    def toggle_user_role(user_id):
        """Переключение роли пользователя"""
        if user_id == session['user_id']:
            flash('Вы не можете изменить свою собственную роль', 'warning')
            return redirect(url_for('admin_users'))

        user = database.get_user_by_id(user_id)
        if not user:
            flash('Пользователь не найден', 'danger')
            return redirect(url_for('admin_users'))

        # Создатель не может быть изменен
        if user['role'] == 'creator':
            flash('Нельзя изменить роль создателя', 'danger')
            return redirect(url_for('admin_users'))

        # Только создатель может назначать/снимать администраторов
        if session.get('role') != 'creator' and user['role'] in ['admin', 'creator']:
            flash('Только создатель может управлять ролями администраторов', 'danger')
            return redirect(url_for('admin_users'))

        new_role = 'user' if user['role'] == 'admin' else 'admin'
        database.update_user_role(user_id, new_role)

        flash(f'Роль пользователя {user["username"]} изменена на "{new_role}"', 'success')
        return redirect(url_for('admin_users'))

    @app.route('/admin/users/<int:user_id>/toggle_status')
    @admin_required
    def toggle_user_status(user_id):
        """Включение/выключение пользователя"""
        if user_id == session['user_id']:
            flash('Вы не можете изменить свой собственный статус', 'warning')
            return redirect(url_for('admin_users'))

        user = database.get_user_by_id(user_id)
        if not user:
            flash('Пользователь не найден', 'danger')
            return redirect(url_for('admin_users'))

        # Нельзя деактивировать создателя
        if user['role'] == 'creator':
            flash('Нельзя деактивировать создателя', 'danger')
            return redirect(url_for('admin_users'))

        # Только создатель может деактивировать администраторов
        if session.get('role') != 'creator' and user['role'] == 'admin':
            flash('Только создатель может деактивировать администраторов', 'danger')
            return redirect(url_for('admin_users'))

        new_status = database.toggle_user_status(user_id)
        status_text = 'активирован' if new_status else 'деактивирован'

        flash(f'Пользователь {user["username"]} {status_text}', 'success')
        return redirect(url_for('admin_users'))

    @app.route('/admin/user/<int:user_id>/actions')
    @creator_required
    def view_user_actions(user_id):
        """Просмотр действий пользователя (только для создателя)"""
        user = database.get_user_by_id(user_id)
        if not user:
            flash('Пользователь не найден', 'danger')
            return redirect(url_for('admin_admins'))

        user_actions = database.get_user_actions(user_id)
        return render_template('user_actions.html', user=user, actions=user_actions)