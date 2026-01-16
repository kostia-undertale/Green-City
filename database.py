import sqlite3
from datetime import datetime
import hashlib
import os


def get_db_path():
    """Получить путь к базе данных"""
    # На Render используем /tmp для записи
    if 'RENDER' in os.environ:
        return '/tmp/green_city.db'
    return 'green_city.db'


def init_db():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()

    # Таблица пользователей
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            city TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица городов
    c.execute('''
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            region TEXT,
            population INTEGER,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица организаций
    c.execute('''
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            org_type TEXT NOT NULL,
            description TEXT,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            city_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_id) REFERENCES cities (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    # Таблица зеленых зон
    c.execute('''
        CREATE TABLE IF NOT EXISTS green_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            zone_type TEXT NOT NULL,
            area REAL,
            location TEXT,
            coordinates TEXT,
            created_by INTEGER,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            approved_by INTEGER,
            approved_date TIMESTAMP,
            rejection_reason TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_id) REFERENCES cities (id),
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (approved_by) REFERENCES users (id)
        )
    ''')

    # Таблица привязки организаций к зонам
    c.execute('''
        CREATE TABLE IF NOT EXISTS zone_organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id INTEGER NOT NULL,
            organization_id INTEGER NOT NULL,
            responsibility_type TEXT, -- maintenance, sponsorship, partnership, etc.
            start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_date TIMESTAMP,
            notes TEXT,
            created_by INTEGER,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zone_id) REFERENCES green_zones (id),
            FOREIGN KEY (organization_id) REFERENCES organizations (id),
            FOREIGN KEY (created_by) REFERENCES users (id),
            UNIQUE(zone_id, organization_id)
        )
    ''')

    # Таблица мероприятий по уходу
    c.execute('''
        CREATE TABLE IF NOT EXISTS maintenance_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id INTEGER,
            city_id INTEGER,
            task_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, in_progress, completed, verification_requested
            priority TEXT DEFAULT 'medium',
            description TEXT,
            created_by INTEGER,
            assigned_to INTEGER,
            assigned_organization INTEGER,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            due_date TIMESTAMP,
            completed_date TIMESTAMP,
            completed_by INTEGER,
            verification_requested_by INTEGER,
            verification_requested_date TIMESTAMP,
            FOREIGN KEY (zone_id) REFERENCES green_zones (id),
            FOREIGN KEY (city_id) REFERENCES cities (id),
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id),
            FOREIGN KEY (assigned_organization) REFERENCES organizations (id),
            FOREIGN KEY (completed_by) REFERENCES users (id),
            FOREIGN KEY (verification_requested_by) REFERENCES users (id)
        )
    ''')

    # Таблица отчетов о состоянии
    c.execute('''
        CREATE TABLE IF NOT EXISTS zone_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id INTEGER,
            city_id INTEGER,
            health_score INTEGER,
            needs_watering BOOLEAN,
            needs_pruning BOOLEAN,
            needs_cleaning BOOLEAN,
            needs_repair BOOLEAN,
            notes TEXT,
            reporter_id INTEGER,
            report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zone_id) REFERENCES green_zones (id),
            FOREIGN KEY (city_id) REFERENCES cities (id),
            FOREIGN KEY (reporter_id) REFERENCES users (id)
        )
    ''')

    # Добавляем тестовые данные
    add_sample_data(c)

    conn.commit()
    conn.close()
    print(f"✅ База данных создана по пути: {get_db_path()}")


def add_sample_data(cursor):
    """Добавление тестовых данных для демонстрации"""
    # Проверяем, есть ли уже данные
    cursor.execute("SELECT COUNT(*) FROM cities")
    if cursor.fetchone()[0] == 0:
        # Добавляем города из списка
        cities = [
            # Алтайский край
            ('Барнаул', 'Алтайский край', 632391),
            ('Бийск', 'Алтайский край', 203108),
            ('Рубцовск', 'Алтайский край', 147002),

            # Волгоградская область
            ('Котельниково', 'Волгоградская область', 22016),

            # Кемеровская область
            ('Ленинск-Кузнецкий', 'Кемеровская область', 97766),
            ('Полысаево', 'Кемеровская область', 26531),
            ('Прокопьевск', 'Кемеровская область', 194084),
            ('Мыски', 'Кемеровская область', 41787),
            ('Кемерово', 'Кемеровская область', 557119),

            # Красноярский край
            ('Бородино', 'Красноярский край', 15824),
            ('Назарово', 'Красноярский край', 49951),
            ('Шарыпово', 'Красноярский край', 37484),

            # Мурманская область
            ('Ковдор', 'Мурманская область', 16439),

            # Ленинградская область
            ('Кингисепп', 'Ленинградская область', 47013),

            # Пермский край
            ('Березники', 'Пермский край', 138069),
            ('Усолье', 'Пермский край', 6614),

            # Республика Хакасия
            ('Абакан', 'Республика Хакасия', 184168),
            ('Черногорск', 'Республика Хакасия', 74422),

            # Свердловская область
            ('Рефтинский', 'Свердловская область', 15671),

            # Хабаровский край
            ('Чегдомын', 'Хабаровский край', 11938)
        ]

        cursor.executemany(
            "INSERT INTO cities (name, region, population) VALUES (?, ?, ?)",
            cities
        )

        # Добавляем тестового создателя
        creator_password = hash_password('creator123')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, city, role) VALUES (?, ?, ?, ?, ?)",
            ('creator', 'creator@greencity.ru', creator_password, 'Ковдор', 'creator')
        )

        # Добавляем тестового администратора
        admin_password = hash_password('admin123')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, city, role) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'admin@greencity.ru', admin_password, 'Барнаул', 'admin')
        )

        # Добавляем тестового обычного пользователя
        user_password = hash_password('user123')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, city, role) VALUES (?, ?, ?, ?, ?)",
            ('user', 'user@greencity.ru', user_password, 'Кемерово', 'user')
        )

        # Добавляем тестовые организации
        test_organizations = [
            ('Экологический фонд "Зеленый город"', 'non-profit', 'Общественная организация по охране окружающей среды',
             'Иванов И.И.', '+7-999-123-45-67', 'eco@greencity.ru', 'https://ecocity.ru', 1, 1),
            ('ООО "Городские услуги"', 'commercial', 'Компания по обслуживанию городских территорий', 'Петров П.П.',
             '+7-999-765-43-21', 'info@cityservice.ru', 'https://cityservice.ru', 1, 1),
            ('Школа №15 Экологический клуб', 'educational', 'Школьный экологический кружок', 'Сидорова С.С.',
             '+7-999-555-44-33', 'school15@edu.ru', 'https://school15.ru', 4, 2),
            ('Волонтерское движение "Чистый город"', 'volunteer', 'Добровольческое объединение', 'Козлов К.К.',
             '+7-999-222-33-44', 'volunteer@clean.ru', 'https://cleanvolunteer.ru', 4, 3),
        ]

        cursor.executemany('''
            INSERT INTO organizations (name, org_type, description, contact_person, phone, email, website, city_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', test_organizations)

        # Добавляем тестовые зеленые зоны для нескольких городов
        test_zones = [
            # Ковдор
            ('Ковдор', 'Центральный парк', 'Парк', 5.2, 'Центр города', '67.566,30.467'),
            ('Ковдор', 'Сквер у ДК', 'Сквер', 1.5, 'ул. Ленина, 10', '67.568,30.470'),

            # Барнаул
            ('Барнаул', 'Нагорный парк', 'Парк', 12.5, 'Центральный район', '53.347,83.779'),
            ('Барнаул', 'Парк Юбилейный', 'Парк', 8.3, 'ул. Юрина', '53.335,83.693'),

            # Кемерово
            ('Кемерово', 'Парк Победы', 'Парк', 15.0, 'Центральный район', '55.354,86.087'),

            # Абакан
            ('Абакан', 'Парк Орлёнок', 'Парк', 6.7, 'Центр города', '53.720,91.442'),

            # Прокопьевск
            ('Прокопьевск', 'Сквер Шахтёров', 'Сквер', 3.2, 'пр. Шахтёров', '53.883,86.720')
        ]

        creator_id = 1  # ID создателя

        for city_name, zone_name, zone_type, area, location, coordinates in test_zones:
            cursor.execute("SELECT id FROM cities WHERE name = ?", (city_name,))
            city = cursor.fetchone()
            if city:
                cursor.execute(
                    "INSERT INTO green_zones (city_id, name, zone_type, area, location, coordinates, created_by, status, approved_by) VALUES (?, ?, ?, ?, ?, ?, ?, 'approved', ?)",
                    (city[0], zone_name, zone_type, area, location, coordinates, creator_id, creator_id)
                )

        # Добавляем тестовые привязки организаций к зонам
        test_zone_orgs = [
            (1, 1, 'maintenance', '2024-01-01', '2024-12-31', 'Основной подрядчик по уходу за парком'),
            (1, 2, 'sponsorship', '2024-01-01', '2024-12-31', 'Спонсорское участие в благоустройстве'),
            (3, 3, 'partnership', '2024-01-01', '2024-12-31', 'Школьный экологический проект'),
            (4, 4, 'volunteer', '2024-01-01', '2024-12-31', 'Волонтерское участие в уборке'),
        ]

        cursor.executemany('''
            INSERT INTO zone_organizations (zone_id, organization_id, responsibility_type, start_date, end_date, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [(z[0], z[1], z[2], z[3], z[4], z[5], 1) for z in test_zone_orgs])

        # Добавляем тестовые задачи
        test_tasks = [
            (1, 1, 'watering', 'pending', 'high', 'Срочный полив деревьев в центральном парке', 2, None, 1, None),
            (1, 1, 'pruning', 'pending', 'medium', 'Обрезка сухих веток', 2, None, 2, None),
            (2, 1, 'cleaning', 'in_progress', 'low', 'Уборка мусора в сквере', 3, None, 4, None),
        ]

        for zone_id, city_id, task_type, status, priority, description, created_by, assigned_to, assigned_organization, due_date in test_tasks:
            cursor.execute(
                "INSERT INTO maintenance_tasks (zone_id, city_id, task_type, status, priority, description, created_by, assigned_to, assigned_organization, due_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (zone_id, city_id, task_type, status, priority, description, created_by, assigned_to,
                 assigned_organization, due_date)
            )

        print("✅ Тестовые данные добавлены в базу данных")


def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, password_hash):
    """Проверка пароля"""
    return hash_password(password) == password_hash


def get_db_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def get_cities():
    """Получить список всех городов"""
    conn = get_db_connection()
    cities = conn.execute('SELECT * FROM cities ORDER BY region, name').fetchall()
    conn.close()
    return cities


def get_all_cities():
    """Получить список всех городов"""
    conn = get_db_connection()
    cities = conn.execute('''
        SELECT * FROM cities 
        ORDER BY region, name
    ''').fetchall()
    conn.close()
    return cities


def get_cities_by_region():
    """Получить города сгруппированные по регионам"""
    conn = get_db_connection()
    cities = conn.execute('SELECT * FROM cities ORDER BY region, name').fetchall()
    conn.close()

    cities_by_region = {}
    for city in cities:
        region = city['region']
        if region not in cities_by_region:
            cities_by_region[region] = []
        cities_by_region[region].append(city)

    return cities_by_region


def get_all_users():
    """Получить список всех пользователей"""
    conn = get_db_connection()
    users = conn.execute('''
        SELECT id, username, email, city, role, is_active, created_date 
        FROM users 
        ORDER BY created_date DESC
    ''').fetchall()
    conn.close()
    return users


def get_admins():
    """Получить список администраторов и создателей"""
    conn = get_db_connection()
    admins = conn.execute('''
        SELECT id, username, email, city, role, is_active, created_date 
        FROM users 
        WHERE role IN ('admin', 'creator')
        ORDER BY role DESC, created_date DESC
    ''').fetchall()
    conn.close()
    return admins


def get_user_by_id(user_id):
    """Получить пользователя по ID"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user


def update_user_role(user_id, new_role):
    """Обновить роль пользователя"""
    conn = get_db_connection()
    conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()


def toggle_user_status(user_id):
    """Включить/выключить пользователя"""
    conn = get_db_connection()
    user = conn.execute('SELECT is_active FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        new_status = 0 if user['is_active'] else 1
        conn.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
        conn.commit()
    conn.close()
    return new_status if user else None


def get_user_actions(user_id):
    """Получить действия пользователя (зоны, отчеты, задачи)"""
    conn = get_db_connection()

    actions = {
        'zones_created': conn.execute('SELECT COUNT(*) FROM green_zones WHERE created_by = ?', (user_id,)).fetchone()[
            0],
        'reports_submitted':
            conn.execute('SELECT COUNT(*) FROM zone_reports WHERE reporter_id = ?', (user_id,)).fetchone()[0],
        'tasks_created':
            conn.execute('SELECT COUNT(*) FROM maintenance_tasks WHERE created_by = ?', (user_id,)).fetchone()[0],
        'recent_zones': conn.execute('''
            SELECT name, created_date FROM green_zones 
            WHERE created_by = ? 
            ORDER BY created_date DESC LIMIT 5
        ''', (user_id,)).fetchall(),
        'recent_reports': conn.execute('''
            SELECT zr.notes, zr.report_date, gz.name as zone_name 
            FROM zone_reports zr 
            JOIN green_zones gz ON zr.zone_id = gz.id 
            WHERE zr.reporter_id = ? 
            ORDER BY zr.report_date DESC LIMIT 5
        ''', (user_id,)).fetchall()
    }

    conn.close()
    return actions


def get_pending_zones():
    """Получить зоны ожидающие модерации"""
    conn = get_db_connection()
    zones = conn.execute('''
        SELECT gz.*, c.name as city_name, u.username as creator_name
        FROM green_zones gz
        JOIN cities c ON gz.city_id = c.id
        JOIN users u ON gz.created_by = u.id
        WHERE gz.status = 'pending'
        ORDER BY gz.created_date DESC
    ''').fetchall()
    conn.close()
    return zones


def approve_zone(zone_id, approved_by_user_id):
    """Одобрить зеленую зону"""
    conn = get_db_connection()
    conn.execute('''
        UPDATE green_zones 
        SET status = 'approved', approved_by = ?, approved_date = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (approved_by_user_id, zone_id))
    conn.commit()
    conn.close()


def reject_zone(zone_id, rejected_by_user_id, reason):
    """Отклонить зеленую зону"""
    conn = get_db_connection()
    conn.execute('''
        UPDATE green_zones 
        SET status = 'rejected', approved_by = ?, rejection_reason = ? 
        WHERE id = ?
    ''', (rejected_by_user_id, reason, zone_id))
    conn.commit()
    conn.close()


def get_approved_zones_for_city(city_name=None, user_city=None):
    """Получить одобренные зоны для города"""
    conn = get_db_connection()

    if city_name:
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
        ''', (city_name,)).fetchall()
    elif user_city:
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
    return zones


def create_task(zone_id, city_id, task_type, description, priority, created_by):
    """Создать новую задачу"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO maintenance_tasks 
        (zone_id, city_id, task_type, description, priority, created_by, status) 
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    ''', (zone_id, city_id, task_type, description, priority, created_by))

    task_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return task_id


def delete_task(task_id):
    """Удалить задачу"""
    conn = get_db_connection()
    conn.execute('DELETE FROM maintenance_tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()


def update_task_status(task_id, status, user_id=None):
    """Обновить статус задачи"""
    conn = get_db_connection()

    if status == 'completed':
        conn.execute('''
            UPDATE maintenance_tasks 
            SET status = ?, completed_by = ?, completed_date = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (status, user_id, task_id))
    elif status == 'verification_requested':
        conn.execute('''
            UPDATE maintenance_tasks 
            SET status = ?, verification_requested_by = ?, verification_requested_date = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (status, user_id, task_id))
    else:
        conn.execute('''
            UPDATE maintenance_tasks 
            SET status = ? 
            WHERE id = ?
        ''', (status, task_id))

    conn.commit()
    conn.close()


def get_tasks_for_zone(zone_id):
    """Получить все задачи для зоны"""
    conn = get_db_connection()
    tasks = conn.execute('''
        SELECT mt.*, u.username as creator_name, 
               cu.username as completed_by_name,
               vu.username as verification_requested_by_name,
               o.name as assigned_organization_name
        FROM maintenance_tasks mt
        LEFT JOIN users u ON mt.created_by = u.id
        LEFT JOIN users cu ON mt.completed_by = cu.id
        LEFT JOIN users vu ON mt.verification_requested_by = vu.id
        LEFT JOIN organizations o ON mt.assigned_organization = o.id
        WHERE mt.zone_id = ?
        ORDER BY mt.priority DESC, mt.created_date DESC
    ''', (zone_id,)).fetchall()
    conn.close()
    return tasks


def get_tasks_awaiting_verification():
    """Получить задачи ожидающие подтверждения выполнения"""
    conn = get_db_connection()
    tasks = conn.execute('''
        SELECT mt.*, gz.name as zone_name, u.username as creator_name,
               vu.username as verification_requested_by_name,
               o.name as assigned_organization_name
        FROM maintenance_tasks mt
        JOIN green_zones gz ON mt.zone_id = gz.id
        LEFT JOIN users u ON mt.created_by = u.id
        LEFT JOIN users vu ON mt.verification_requested_by = vu.id
        LEFT JOIN organizations o ON mt.assigned_organization = o.id
        WHERE mt.status = 'verification_requested'
        ORDER BY mt.verification_requested_date DESC
    ''').fetchall()
    conn.close()
    return tasks


# Новые функции для работы с организациями

def get_organizations_for_city(city_id):
    """Получить организации для конкретного города"""
    conn = get_db_connection()
    organizations = conn.execute('''
        SELECT o.*, u.username as creator_name, c.name as city_name
        FROM organizations o
        LEFT JOIN users u ON o.created_by = u.id
        LEFT JOIN cities c ON o.city_id = c.id
        WHERE o.city_id = ? AND o.is_active = 1
        ORDER BY o.name
    ''', (city_id,)).fetchall()
    conn.close()
    return organizations


def get_all_organizations():
    """Получить все организации"""
    conn = get_db_connection()
    organizations = conn.execute('''
        SELECT o.*, u.username as creator_name, c.name as city_name
        FROM organizations o
        LEFT JOIN users u ON o.created_by = u.id
        LEFT JOIN cities c ON o.city_id = c.id
        ORDER BY o.city_id, o.name
    ''').fetchall()
    conn.close()
    return organizations


def create_organization(name, org_type, description, contact_person, phone, email, website, city_id, created_by):
    """Создать новую организацию"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO organizations 
        (name, org_type, description, contact_person, phone, email, website, city_id, created_by) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, org_type, description, contact_person, phone, email, website, city_id, created_by))

    org_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return org_id


def get_zone_organizations(zone_id):
    """Получить организации, привязанные к зоне"""
    conn = get_db_connection()
    organizations = conn.execute('''
        SELECT zo.*, o.name as organization_name, o.org_type, o.description, 
               o.contact_person, o.phone, o.email, o.website,
               u.username as created_by_name
        FROM zone_organizations zo
        JOIN organizations o ON zo.organization_id = o.id
        LEFT JOIN users u ON zo.created_by = u.id
        WHERE zo.zone_id = ?
        ORDER BY zo.start_date DESC
    ''', (zone_id,)).fetchall()
    conn.close()
    return organizations


def add_organization_to_zone(zone_id, organization_id, responsibility_type, notes, created_by):
    """Привязать организацию к зоне"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверяем, нет ли уже такой привязки
    existing = conn.execute('''
        SELECT id FROM zone_organizations 
        WHERE zone_id = ? AND organization_id = ?
    ''', (zone_id, organization_id)).fetchone()

    if existing:
        conn.close()
        return False  # Привязка уже существует

    cursor.execute('''
        INSERT INTO zone_organizations 
        (zone_id, organization_id, responsibility_type, notes, created_by) 
        VALUES (?, ?, ?, ?, ?)
    ''', (zone_id, organization_id, responsibility_type, notes, created_by))

    conn.commit()
    conn.close()
    return True


def remove_organization_from_zone(zone_id, organization_id):
    """Отвязать организацию от зоны"""
    conn = get_db_connection()
    conn.execute('''
        DELETE FROM zone_organizations 
        WHERE zone_id = ? AND organization_id = ?
    ''', (zone_id, organization_id))
    conn.commit()
    conn.close()


def get_organizations_for_task_assignment(city_id):
    """Получить организации для назначения задач"""
    conn = get_db_connection()
    organizations = conn.execute('''
        SELECT o.* 
        FROM organizations o
        WHERE (o.city_id = ? OR o.city_id IS NULL) AND o.is_active = 1
        ORDER BY o.name
    ''', (city_id,)).fetchall()
    conn.close()
    return organizations