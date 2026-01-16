import sqlite3
import os

def add_test_zones():
    """Добавляем тестовые зеленые зоны с реальными координатами"""
    if 'RENDER' in os.environ:
        db_path = '/tmp/green_city.db'
    else:
        db_path = 'green_city.db'

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Получаем ID города Ковдор
    c.execute("SELECT id FROM cities WHERE name = 'Ковдор'")
    kovdor_id = c.fetchone()[0]

    # Получаем ID пользователя admin
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    admin_id = c.fetchone()[0]

    # Тестовые зеленые зоны для Ковдора с реальными координатами
    test_zones = [
        ('Центральный парк', 'Парк', 5.2, 'Центр города', '67.5660,30.4670', kovdor_id, admin_id),
        ('Сквер у Дворца культуры', 'Сквер', 1.5, 'ул. Ленина, 10', '67.5680,30.4700', kovdor_id, admin_id),
        ('Парк Горняков', 'Парк', 3.8, 'пр. Горняков, 25', '67.5650,30.4720', kovdor_id, admin_id),
        (
        'Детская площадка "Солнышко"', 'Детская площадка', 0.3, 'микрорайон 3', '67.5700,30.4650', kovdor_id, admin_id),
        ('Сквер Победы', 'Сквер', 2.1, 'ул. Мира, 15', '67.5630,30.4690', kovdor_id, admin_id),
    ]

    # Очищаем старые тестовые зоны (опционально)
    c.execute("DELETE FROM green_zones WHERE created_by = ?", (admin_id,))

    # Добавляем новые зоны
    c.executemany(
        "INSERT INTO green_zones (name, zone_type, area, location, coordinates, city_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        test_zones
    )

    # Добавляем тестовые отчеты
    zones = c.execute("SELECT id FROM green_zones").fetchall()
    for zone_id in zones:
        c.execute(
            """INSERT INTO zone_reports 
               (zone_id, city_id, health_score, needs_watering, needs_pruning, needs_cleaning, needs_repair, notes, reporter_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (zone_id[0], kovdor_id, 75, 0, 1, 0, 0, 'Состояние хорошее, требуется обрезка', admin_id)
        )

    conn.commit()
    conn.close()
    print("✅ Тестовые зеленые зоны успешно добавлены!")


if __name__ == '__main__':
    add_test_zones()