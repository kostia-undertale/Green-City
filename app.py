import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import database
import auth
import maps
import sys

app = Flask(__name__)

# Конфигурация для продакшена
if os.environ.get('RENDER'):
    # На Render используем переменные окружения
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    print("🚀 Запуск в режиме Render (продакшн)")
else:
    app.secret_key = 'dev-secret-key-change-in-production'
    print("💻 Запуск в режиме разработки")


# Инициализация базы данных при запуске
def initialize_database():
    """Инициализация базы данных"""
    try:
        if not os.path.exists(database.get_db_path()):
            print("📊 Инициализация базы данных...")
            database.init_db()
            print("✅ База данных инициализирована")
    except Exception as e:
        print(f"⚠️ Ошибка при инициализации БД: {e}")

initialize_database()


app.secret_key = 'your-secret-key-here-change-in-production'

# Инициализация маршрутов аутентификации
auth.init_auth_routes(app)

# Инициализация базы данных при запуске
if not os.path.exists('green_city.db'):
    database.init_db()


def get_user_city():
    """Получить город текущего пользователя"""
    return session.get('city', None)

def login_required(f):
    """Декоратор для проверки авторизации"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/')
def index():
    """Главная страница с общей статистикой"""
    user_city = get_user_city()
    conn = database.get_db_connection()

    if user_city:
        # Статистика для конкретного города
        city_stats = conn.execute('''
            SELECT 
                COUNT(DISTINCT gz.id) as total_zones,
                COUNT(CASE WHEN mt.status = "pending" THEN 1 END) as pending_tasks,
                COUNT(CASE WHEN mt.priority = "high" AND mt.status = "pending" THEN 1 END) as critical_tasks,
                COALESCE(AVG(zr.health_score), 0) as avg_health,
                COUNT(DISTINCT o.id) as total_organizations
            FROM green_zones gz
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN organizations o ON gz.city_id = o.city_id
            WHERE gz.city_id = (SELECT id FROM cities WHERE name = ?)
            AND gz.status = 'approved'
        ''', (user_city,)).fetchone()

        stats = {
            'total_zones': city_stats['total_zones'],
            'pending_tasks': city_stats['pending_tasks'],
            'critical_tasks': city_stats['critical_tasks'],
            'avg_health': city_stats['avg_health'],
            'total_organizations': city_stats['total_organizations'] or 0
        }

        # Последние задачи для города
        recent_tasks = conn.execute('''
            SELECT mt.*, gz.name as zone_name 
            FROM maintenance_tasks mt 
            JOIN green_zones gz ON mt.zone_id = gz.id 
            WHERE gz.city_id = (SELECT id FROM cities WHERE name = ?)
            AND gz.status = 'approved'
            ORDER BY mt.created_date DESC 
            LIMIT 5
        ''', (user_city,)).fetchall()

    else:
        # Если пользователь не авторизован, показываем общую статистику
        if 'user_id' in session:
            # Пользователь авторизован, но почему-то нет города в сессии
            conn.execute('SELECT city FROM users WHERE id = ?', (session['user_id'],))
            user_city_result = conn.fetchone()
            if user_city_result:
                session['city'] = user_city_result['city']
                return redirect(url_for('index'))

        # Общая статистика по всем городам для неавторизованных
        stats = {
            'total_zones': conn.execute("SELECT COUNT(*) FROM green_zones WHERE status = 'approved'").fetchone()[0],
            'pending_tasks': conn.execute("SELECT COUNT(*) FROM maintenance_tasks WHERE status = 'pending'").fetchone()[
                0],
            'critical_tasks': conn.execute(
                "SELECT COUNT(*) FROM maintenance_tasks WHERE priority = 'high' AND status = 'pending'").fetchone()[0],
            'avg_health': conn.execute('SELECT AVG(health_score) FROM zone_reports').fetchone()[0] or 0,
            'total_organizations': conn.execute("SELECT COUNT(*) FROM organizations WHERE is_active = 1").fetchone()[0]
        }

        recent_tasks = conn.execute('''
            SELECT mt.*, gz.name as zone_name 
            FROM maintenance_tasks mt 
            JOIN green_zones gz ON mt.zone_id = gz.id 
            WHERE gz.status = 'approved'
            ORDER BY mt.created_date DESC 
            LIMIT 5
        ''').fetchall()

    conn.close()

    return render_template('index.html', stats=stats, recent_tasks=recent_tasks, user_city=user_city)


@app.route('/map')
def map_view():
    """Интерактивная карта с зелеными зонами"""
    user_city = get_user_city()

    conn = database.get_db_connection()

    if user_city:
        zones = conn.execute('''
            SELECT gz.*, 
                   COALESCE(AVG(zr.health_score), 0) as avg_health,
                   COUNT(CASE WHEN mt.status = "pending" THEN 1 END) as pending_tasks
            FROM green_zones gz
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id
            WHERE gz.city_id = (SELECT id FROM cities WHERE name = ?)
            AND gz.status = 'approved'
            GROUP BY gz.id
        ''', (user_city,)).fetchall()
    else:
        zones = conn.execute('''
            SELECT gz.*, 
                   COALESCE(AVG(zr.health_score), 0) as avg_health,
                   COUNT(CASE WHEN mt.status = "pending" THEN 1 END) as pending_tasks
            FROM green_zones gz
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id
            WHERE gz.status = 'approved'
            GROUP BY gz.id
        ''').fetchall()

    conn.close()

    # Преобразуем Row объекты в словари для удобства
    zones_list = []
    for zone in zones:
        zones_list.append({
            'id': zone['id'],
            'name': zone['name'],
            'zone_type': zone['zone_type'],
            'area': zone['area'],
            'location': zone['location'],
            'coordinates': zone['coordinates'],
            'avg_health': zone['avg_health'] or 0,
            'pending_tasks': zone['pending_tasks'] or 0
        })

    print(f"📍 Found {len(zones_list)} zones in database")
    for zone in zones_list:
        print(f"📍 Zone: {zone['name']}, Coords: {zone['coordinates']}")

    # Генерируем карту
    map_html = maps.generate_map_with_zones(zones_list, user_city)

    return render_template('map.html', zones=zones_list, user_city=user_city, map_html=map_html)


@app.route('/fullscreen_map')
def fullscreen_map():
    """Полноэкранная карта"""
    user_city = get_user_city()
    tile_provider = request.args.get('tile', 'openstreetmap')

    conn = database.get_db_connection()

    if user_city:
        zones = conn.execute('''
            SELECT gz.*, 
                   COALESCE(AVG(zr.health_score), 0) as avg_health,
                   COUNT(CASE WHEN mt.status = "pending" THEN 1 END) as pending_tasks
            FROM green_zones gz
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id
            WHERE gz.city_id = (SELECT id FROM cities WHERE name = ?)
            AND gz.status = 'approved'
            GROUP BY gz.id
        ''', (user_city,)).fetchall()
    else:
        zones = conn.execute('''
            SELECT gz.*, 
                   COALESCE(AVG(zr.health_score), 0) as avg_health,
                   COUNT(CASE WHEN mt.status = "pending" THEN 1 END) as pending_tasks
            FROM green_zones gz
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id
            WHERE gz.status = 'approved'
            GROUP BY gz.id
        ''').fetchall()

    # Преобразуем Row объекты в словари для удобства
    zones_list = []
    for zone in zones:
        zones_list.append({
            'id': zone['id'],
            'name': zone['name'],
            'zone_type': zone['zone_type'],
            'area': zone['area'],
            'location': zone['location'],
            'coordinates': zone['coordinates'],
            'avg_health': zone['avg_health'],
            'pending_tasks': zone['pending_tasks']
        })

    conn.close()

    # Генерируем полноэкранную карту
    map_html = maps.MapService.generate_leaflet_map(zones_list, tile_provider=tile_provider)

    return map_html


@app.route('/add_zone', methods=['GET', 'POST'])
@login_required
def add_zone():
    """Добавление новой зеленой зоны"""
    user_city = get_user_city()
    if not user_city:
        flash('Ошибка: город не выбран', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        zone_type = request.form['zone_type']
        area = request.form['area']
        location = request.form['location']
        coordinates = request.form['coordinates']

        # Проверяем что координаты есть
        if not coordinates:
            flash('Ошибка: не выбрано местоположение на карте', 'error')
            return redirect(url_for('add_zone'))

        conn = database.get_db_connection()

        # Получаем ID города
        city = conn.execute('SELECT id FROM cities WHERE name = ?', (user_city,)).fetchone()
        if not city:
            flash('Город не найден', 'error')
            conn.close()
            return redirect(url_for('index'))

        # Определяем статус зоны в зависимости от роли пользователя
        user_role = session.get('role', 'user')
        if user_role in ['admin', 'creator']:
            status = 'approved'
            approved_by = session['user_id']
        else:
            status = 'pending'
            approved_by = None

        # Вставляем новую зону
        conn.execute(
            'INSERT INTO green_zones (city_id, name, zone_type, area, location, coordinates, created_by, status, approved_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (city['id'], name, zone_type, area, location, coordinates, session['user_id'], status, approved_by)
        )
        conn.commit()
        conn.close()

        if user_role in ['admin', 'creator']:
            flash('Зеленая зона успешно создана!', 'success')
        else:
            flash('Зеленая зона успешно создана и отправлена на модерацию!', 'success')

        return redirect(url_for('map_view'))

    # Получаем координаты города для центра карты
    city_coords = maps.MapService.get_nominatim_coordinates(user_city)
    default_coords = ""
    if city_coords:
        default_coords = f"{city_coords['lat']:.6f},{city_coords['lon']:.6f}"

    return render_template('add_zone.html', user_city=user_city, default_coords=default_coords)


@app.route('/zone/<int:zone_id>')
def zone_detail(zone_id):
    """Детальная информация о зеленой зоне"""
    conn = database.get_db_connection()

    zone = conn.execute('''
        SELECT gz.*, c.name as city_name 
        FROM green_zones gz 
        JOIN cities c ON gz.city_id = c.id 
        WHERE gz.id = ?
    ''', (zone_id,)).fetchone()

    if not zone:
        flash('Зеленая зона не найдена', 'danger')
        conn.close()
        return redirect(url_for('map_view'))

    # Проверяем доступ к зоне
    if zone['status'] != 'approved' and session.get('role') not in ['admin', 'creator']:
        flash('Эта зона еще не прошла модерацию', 'warning')
        conn.close()
        return redirect(url_for('map_view'))

    tasks = database.get_tasks_for_zone(zone_id)
    reports = conn.execute('''
        SELECT zr.*, u.username as reporter_name
        FROM zone_reports zr
        LEFT JOIN users u ON zr.reporter_id = u.id
        WHERE zone_id = ? 
        ORDER BY report_date DESC
    ''', (zone_id,)).fetchall()

    # Получаем привязанные организации
    zone_organizations = database.get_zone_organizations(zone_id)

    # Получаем доступные организации для привязки (администраторам)
    available_organizations = []
    if session.get('role') in ['admin', 'creator']:
        available_organizations = database.get_all_organizations()

    # Получаем организации для назначения задач
    organizations_for_assignment = []
    if session.get('role') in ['admin', 'creator']:
        organizations_for_assignment = database.get_organizations_for_task_assignment(zone['city_id'])

    # Получаем все города для создания организации
    cities = database.get_cities()

    conn.close()

    return render_template('zone_detail.html',
                           zone=zone,
                           tasks=tasks,
                           reports=reports,
                           zone_organizations=zone_organizations,
                           available_organizations=available_organizations,
                           organizations_for_assignment=organizations_for_assignment,
                           cities=cities)


@app.route('/delete_zone/<int:zone_id>', methods=['POST'])
@admin_required
def delete_zone(zone_id):
    """Удаление зеленой зоны (только для администраторов и создателя)"""
    conn = database.get_db_connection()

    # Проверяем существование зоны
    zone = conn.execute('SELECT * FROM green_zones WHERE id = ?', (zone_id,)).fetchone()
    if not zone:
        flash('Зеленая зона не найдена', 'danger')
        conn.close()
        return redirect(url_for('map_view'))

    # Удаляем связанные данные (отчеты и задачи)
    try:
        # Удаляем отчеты о зоне
        conn.execute('DELETE FROM zone_reports WHERE zone_id = ?', (zone_id,))

        # Удаляем привязки организаций
        conn.execute('DELETE FROM zone_organizations WHERE zone_id = ?', (zone_id,))

        # Удаляем задачи по зоне
        conn.execute('DELETE FROM maintenance_tasks WHERE zone_id = ?', (zone_id,))

        # Удаляем саму зону
        conn.execute('DELETE FROM green_zones WHERE id = ?', (zone_id,))

        conn.commit()
        flash(f'Зеленая зона "{zone["name"]}" успешно удалена', 'success')

    except Exception as e:
        conn.rollback()
        flash('Ошибка при удалении зоны', 'danger')
        print(f"Error deleting zone: {e}")

    conn.close()
    return redirect(url_for('map_view'))


@app.route('/moderate_zones')
@admin_required
def moderate_zones():
    """Страница модерации зеленых зон"""
    pending_zones = database.get_pending_zones()
    return render_template('moderate_zones.html', pending_zones=pending_zones)


@app.route('/approve_zone/<int:zone_id>')
@admin_required
def approve_zone(zone_id):
    """Одобрить зеленую зону"""
    database.approve_zone(zone_id, session['user_id'])
    flash('Зеленая зона успешно одобрена!', 'success')
    return redirect(url_for('moderate_zones'))


@app.route('/reject_zone/<int:zone_id>', methods=['POST'])
@admin_required
def reject_zone(zone_id):
    """Отклонить зеленую зону"""
    reason = request.form.get('reason', '')
    database.reject_zone(zone_id, session['user_id'], reason)
    flash('Зеленая зона отклонена', 'info')
    return redirect(url_for('moderate_zones'))


@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    """Добавление новой задачи"""
    zone_id = request.form['zone_id']
    task_type = request.form['task_type']
    description = request.form['description']
    priority = request.form['priority']
    assigned_organization = request.form.get('assigned_organization')

    conn = database.get_db_connection()

    # Проверяем что зона существует и одобрена
    zone = conn.execute('SELECT id, city_id FROM green_zones WHERE id = ? AND status = "approved"',
                        (zone_id,)).fetchone()
    if not zone:
        flash('Зона не найдена или не одобрена', 'danger')
        conn.close()
        return redirect(url_for('zone_detail', zone_id=zone_id))

    # Создаем задачу
    task_id = database.create_task(
        zone_id=zone_id,
        city_id=zone['city_id'],
        task_type=task_type,
        description=description,
        priority=priority,
        created_by=session['user_id']
    )

    # Если указана организация, назначаем её на задачу
    if assigned_organization and assigned_organization.isdigit():
        conn.execute('''
            UPDATE maintenance_tasks 
            SET assigned_organization = ? 
            WHERE id = ?
        ''', (int(assigned_organization), task_id))
        conn.commit()

    conn.close()

    flash('Задача успешно создана!', 'success')
    return redirect(url_for('zone_detail', zone_id=zone_id))


@app.route('/delete_task/<int:task_id>', methods=['POST'])
@admin_required
def delete_task(task_id):
    """Удаление задачи (только для администраторов и создателя)"""
    conn = database.get_db_connection()

    # Получаем информацию о задаче для редиректа
    task = conn.execute('SELECT zone_id FROM maintenance_tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        flash('Задача не найдена', 'danger')
        conn.close()
        return redirect(url_for('index'))

    zone_id = task['zone_id']

    # Удаляем задачу
    database.delete_task(task_id)

    conn.close()
    flash('Задача успешно удалена!', 'success')
    return redirect(url_for('zone_detail', zone_id=zone_id))


@app.route('/update_task_status/<int:task_id>/<status>')
@login_required
def update_task_status(task_id, status):
    """Обновление статуса задачи"""
    conn = database.get_db_connection()

    # Получаем информацию о задаче
    task = conn.execute('SELECT zone_id FROM maintenance_tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        flash('Задача не найдена', 'danger')
        conn.close()
        return redirect(url_for('index'))

    zone_id = task['zone_id']

    # Обновляем статус задачи
    if status == 'verification_requested':
        # Любой пользователь может запросить подтверждение выполнения
        database.update_task_status(task_id, status, session['user_id'])
        flash('Запрос на подтверждение выполнения отправлен!', 'success')
    elif status == 'completed' and session.get('role') in ['admin', 'creator']:
        # Только админы могут подтвердить выполнение
        database.update_task_status(task_id, status, session['user_id'])
        flash('Задача отмечена как выполненная!', 'success')
    elif status in ['pending', 'in_progress'] and session.get('role') in ['admin', 'creator']:
        # Только админы могут менять статус на pending/in_progress
        database.update_task_status(task_id, status)
        flash('Статус задачи обновлен!', 'success')
    else:
        flash('Недостаточно прав для этого действия', 'danger')

    conn.close()
    return redirect(url_for('zone_detail', zone_id=zone_id))


@app.route('/task_verification')
@admin_required
def task_verification():
    """Страница подтверждения выполнения задач"""
    tasks_awaiting_verification = database.get_tasks_awaiting_verification()
    return render_template('task_verification.html', tasks=tasks_awaiting_verification)


@app.route('/add_report', methods=['POST'])
@login_required
def add_report():
    """Добавление отчета о состоянии зоны"""
    zone_id = request.form['zone_id']
    health_score = request.form['health_score']
    needs_watering = 1 if 'needs_watering' in request.form else 0
    needs_pruning = 1 if 'needs_pruning' in request.form else 0
    needs_cleaning = 1 if 'needs_cleaning' in request.form else 0
    needs_repair = 1 if 'needs_repair' in request.form else 0
    notes = request.form['notes']

    conn = database.get_db_connection()

    # Проверяем что зона одобрена
    zone = conn.execute('SELECT status FROM green_zones WHERE id = ?', (zone_id,)).fetchone()
    if not zone or zone['status'] != 'approved':
        flash('Нельзя добавить отчет для неодобренной зоны', 'danger')
        conn.close()
        return redirect(url_for('map_view'))

    # Получаем информацию о зоне для city_id
    zone_info = conn.execute('SELECT city_id FROM green_zones WHERE id = ?', (zone_id,)).fetchone()

    conn.execute(
        '''INSERT INTO zone_reports 
           (zone_id, city_id, health_score, needs_watering, needs_pruning, needs_cleaning, needs_repair, notes, reporter_id) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
        zone_id, zone_info['city_id'], health_score, needs_watering, needs_pruning, needs_cleaning, needs_repair, notes,
        session['user_id'])
    )

    conn.commit()
    conn.close()

    flash('Отчет успешно добавлен!', 'success')
    return redirect(url_for('zone_detail', zone_id=zone_id))


@app.route('/reports')
def reports():
    """Страница с аналитикой и отчетами"""
    user_city = get_user_city()
    conn = database.get_db_connection()

    if user_city:
        # Статистика для выбранного города
        task_stats = conn.execute('''
            SELECT task_type, status, COUNT(*) as count 
            FROM maintenance_tasks 
            WHERE city_id = (SELECT id FROM cities WHERE name = ?)
            GROUP BY task_type, status
        ''', (user_city,)).fetchall()

        health_stats = conn.execute('''
            SELECT 
                CASE 
                    WHEN health_score >= 80 THEN 'Отлично'
                    WHEN health_score >= 60 THEN 'Хорошо'
                    WHEN health_score >= 40 THEN 'Удовлетворительно'
                    ELSE 'Плохо'
                END as health_category,
                COUNT(*) as count
            FROM zone_reports
            WHERE city_id = (SELECT id FROM cities WHERE name = ?)
            GROUP BY health_category
        ''', (user_city,)).fetchall()

        # Самые проблемные зоны
        problem_zones = conn.execute('''
            SELECT gz.name, AVG(zr.health_score) as avg_health, COUNT(mt.id) as pending_tasks
            FROM green_zones gz
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id AND mt.status = 'pending'
            WHERE gz.city_id = (SELECT id FROM cities WHERE name = ?)
            AND gz.status = 'approved'
            GROUP BY gz.id
            HAVING avg_health < 60 OR pending_tasks > 0
            ORDER BY avg_health ASC, pending_tasks DESC
            LIMIT 5
        ''', (user_city,)).fetchall()
    else:
        # Общая статистика по всем городам
        task_stats = conn.execute('''
            SELECT task_type, status, COUNT(*) as count 
            FROM maintenance_tasks 
            GROUP BY task_type, status
        ''').fetchall()

        health_stats = conn.execute('''
            SELECT 
                CASE 
                    WHEN health_score >= 80 THEN 'Отлично'
                    WHEN health_score >= 60 THEN 'Хорошо'
                    WHEN health_score >= 40 THEN 'Удовлетворительно'
                    ELSE 'Плохо'
                END as health_category,
                COUNT(*) as count
            FROM zone_reports
            GROUP BY health_category
        ''').fetchall()

        # Самые проблемные зоны
        problem_zones = conn.execute('''
            SELECT gz.name, c.name as city_name, AVG(zr.health_score) as avg_health, COUNT(mt.id) as pending_tasks
            FROM green_zones gz
            JOIN cities c ON gz.city_id = c.id
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id AND mt.status = 'pending'
            WHERE gz.status = 'approved'
            GROUP BY gz.id
            HAVING avg_health < 60 OR pending_tasks > 0
            ORDER BY avg_health ASC, pending_tasks DESC
            LIMIT 5
        ''').fetchall()

    conn.close()

    return render_template('reports.html',
                           task_stats=task_stats,
                           health_stats=health_stats,
                           problem_zones=problem_zones,
                           user_city=user_city)


# Новые маршруты для работы с организациями

@app.route('/create_organization', methods=['POST'])
@admin_required
def create_organization():
    """Создание новой организации"""
    name = request.form['name']
    org_type = request.form['org_type']
    description = request.form.get('description', '')
    contact_person = request.form.get('contact_person', '')
    phone = request.form.get('phone', '')
    email = request.form.get('email', '')
    website = request.form.get('website', '')
    city_id = request.form['city_id']
    zone_id = request.form.get('zone_id')

    if not name or not org_type or not city_id:
        flash('Пожалуйста, заполните все обязательные поля', 'danger')
        return redirect(url_for('zone_detail', zone_id=zone_id) if zone_id else url_for('index'))

    organization_id = database.create_organization(
        name=name,
        org_type=org_type,
        description=description,
        contact_person=contact_person,
        phone=phone,
        email=email,
        website=website,
        city_id=city_id,
        created_by=session['user_id']
    )

    flash(f'Организация "{name}" успешно создана!', 'success')

    if zone_id:
        # Редирект с параметром для автоматического открытия модального окна привязки
        return redirect(url_for('zone_detail', zone_id=zone_id, organization_created='true'))

    return redirect(url_for('index'))


@app.route('/add_organization_to_zone/<int:zone_id>', methods=['POST'])
@admin_required
def add_organization_to_zone(zone_id):
    """Привязать организацию к зоне"""
    organization_id = request.form['organization_id']
    responsibility_type = request.form['responsibility_type']
    notes = request.form.get('notes', '')

    if not organization_id or not responsibility_type:
        flash('Пожалуйста, выберите организацию и тип ответственности', 'danger')
        return redirect(url_for('zone_detail', zone_id=zone_id))

    success = database.add_organization_to_zone(
        zone_id=zone_id,
        organization_id=organization_id,
        responsibility_type=responsibility_type,
        notes=notes,
        created_by=session['user_id']
    )

    if success:
        flash('Организация успешно привязана к зоне!', 'success')
    else:
        flash('Эта организация уже привязана к данной зоне', 'warning')

    return redirect(url_for('zone_detail', zone_id=zone_id))


@app.route('/remove_organization_from_zone/<int:zone_id>/<int:organization_id>', methods=['POST'])
@admin_required
def remove_organization_from_zone(zone_id, organization_id):
    """Отвязать организацию от зоны"""
    database.remove_organization_from_zone(zone_id, organization_id)
    flash('Организация успешно отвязана от зоны', 'success')
    return redirect(url_for('zone_detail', zone_id=zone_id))


@app.route('/admin/organizations')
@admin_required
def admin_organizations():
    """Админ-панель: управление организациями"""
    organizations = database.get_all_organizations()
    cities = database.get_cities()
    return render_template('admin_organizations.html', organizations=organizations, cities=cities)


@app.route('/api/zones')
def api_zones():
    """API для получения данных о зонах"""
    user_city = get_user_city()
    conn = database.get_db_connection()

    if user_city:
        zones = conn.execute('''
            SELECT gz.*, c.name as city_name,
                   COALESCE(AVG(zr.health_score), 0) as avg_health,
                   COUNT(CASE WHEN mt.status = "pending" THEN 1 END) as pending_tasks
            FROM green_zones gz
            JOIN cities c ON gz.city_id = c.id
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id
            WHERE c.name = ?
            AND gz.status = 'approved'
            GROUP BY gz.id
        ''', (user_city,)).fetchall()
    else:
        zones = conn.execute('''
            SELECT gz.*, c.name as city_name,
                   COALESCE(AVG(zr.health_score), 0) as avg_health,
                   COUNT(CASE WHEN mt.status = "pending" THEN 1 END) as pending_tasks
            FROM green_zones gz
            JOIN cities c ON gz.city_id = c.id
            LEFT JOIN zone_reports zr ON gz.id = zr.zone_id
            LEFT JOIN maintenance_tasks mt ON gz.id = mt.zone_id
            WHERE gz.status = 'approved'
            GROUP BY gz.id
        ''').fetchall()

    zones_list = []
    for zone in zones:
        zones_list.append({
            'id': zone['id'],
            'name': zone['name'],
            'type': zone['zone_type'],
            'area': zone['area'],
            'location': zone['location'],
            'coordinates': zone['coordinates'],
            'city': zone['city_name'],
            'health_score': round(zone['avg_health']),
            'pending_tasks': zone['pending_tasks']
        })

    conn.close()
    return jsonify(zones_list)


@app.route('/api/city_coordinates/<city_name>')
def api_city_coordinates(city_name):
    """API для получения координат города"""
    coordinates = maps.MapService.get_nominatim_coordinates(city_name)
    if coordinates:
        return jsonify({
            'success': True,
            'coordinates': coordinates
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Координаты не найдены'
        }), 404


@app.route('/api/city_suggestions')
def api_city_suggestions():
    """API для автозаполнения городов"""
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])

    suggestions = maps.MapService.get_city_suggestions(query)
    return jsonify(suggestions)


@app.route('/api/geocode')
def api_geocode():
    """API для геокодирования адреса"""
    address = request.args.get('address', '')
    city = request.args.get('city', '')

    if not address:
        return jsonify({'success': False, 'message': 'Адрес не указан'}), 400

    result = maps.MapService.geocode_address(address, city)
    if result:
        return jsonify({
            'success': True,
            'coordinates': result
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Адрес не найден'
        }), 404


@app.route('/api/reverse_geocode')
def api_reverse_geocode():
    """API для обратного геокодирования (получение адреса по координатам)"""
    lat = request.args.get('lat', '')
    lon = request.args.get('lon', '')

    if not lat or not lon:
        return jsonify({'success': False, 'message': 'Координаты не указаны'}), 400

    try:
        address = maps.MapService.reverse_geocode(float(lat), float(lon))
        if address:
            return jsonify({
                'success': True,
                'address': address
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Адрес не найден'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка при определении адреса: {str(e)}'
        }), 500


@app.route('/map_demo')
def map_demo():
    """Демонстрационная страница с разными картами"""
    return render_template('map_demo.html')


# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    conn = database.get_db_connection()
    conn.close()
    return render_template('500.html'), 500


@app.context_processor
def inject_moderation_link():
    def has_pending_zones():
        if session.get('role') in ['admin', 'creator']:
            pending_zones = database.get_pending_zones()
            return len(pending_zones) > 0
        return False

    def get_pending_zones_count():
        if session.get('role') in ['admin', 'creator']:
            pending_zones = database.get_pending_zones()
            return len(pending_zones)
        return 0

    def has_tasks_awaiting_verification():
        if session.get('role') in ['admin', 'creator']:
            tasks = database.get_tasks_awaiting_verification()
            return len(tasks) > 0
        return False

    def get_tasks_awaiting_verification_count():
        if session.get('role') in ['admin', 'creator']:
            tasks = database.get_tasks_awaiting_verification()
            return len(tasks)
        return 0

    return dict(
        has_pending_zones=has_pending_zones,
        get_pending_zones_count=get_pending_zones_count,
        has_tasks_awaiting_verification=has_tasks_awaiting_verification,
        get_tasks_awaiting_verification_count=get_tasks_awaiting_verification_count,
        database=database
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    app.run(host='0.0.0.0', port=port, debug=False)
