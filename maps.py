import json


def generate_map_with_zones(zones, user_city=None):
    """Генерация карты с зонами - упрощенная версия"""

    # Фильтруем зоны с валидными координатами
    valid_zones = []
    for zone in zones:
        coords = zone.get('coordinates')
        if coords:
            try:
                # Очищаем координаты
                coords_clean = coords.strip().replace(' ', '')
                if ',' in coords_clean:
                    lat_str, lon_str = coords_clean.split(',')
                    lat, lon = float(lat_str), float(lon_str)

                    # Проверяем валидность координат
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        valid_zones.append({
                            'id': zone['id'],
                            'name': zone['name'],
                            'zone_type': zone.get('zone_type', 'Неизвестно'),
                            'area': zone.get('area', 0),
                            'health_score': zone.get('avg_health', 0) or 0,
                            'pending_tasks': zone.get('pending_tasks', 0),
                            'location': zone.get('location', 'Не указано'),
                            'lat': lat,
                            'lon': lon
                        })
            except (ValueError, IndexError, AttributeError) as e:
                print(f"❌ Error processing zone {zone.get('name')}: {e}")
                continue

    print(f"🎯 Valid zones for map: {len(valid_zones)}")

    # Определяем центр карты
    if valid_zones:
        avg_lat = sum(z['lat'] for z in valid_zones) / len(valid_zones)
        avg_lon = sum(z['lon'] for z in valid_zones) / len(valid_zones)
        center_lat, center_lon = avg_lat, avg_lon
        zoom = 12
    else:
        # Центр по умолчанию - Москва
        center_lat, center_lon = 55.7558, 37.6173
        zoom = 5

    # Генерируем HTML карты
    map_html = f'''
    <div class="card">
        <div class="card-header bg-success text-white">
            <h5 class="mb-0">
                <i class="fas fa-map-marked-alt me-2"></i>Карта зеленых зон
                <span class="badge bg-light text-success ms-2">{len(valid_zones)}</span>
            </h5>
        </div>
        <div class="card-body p-0">
            <div id="greenZonesMap" style="height: 500px; border-radius: 0 0 8px 8px;"></div>
        </div>
    </div>

    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Инициализация карты с отключенной атрибуцией
        var map = L.map('greenZonesMap', {{
            attributionControl: false
        }}).setView([{center_lat}, {center_lon}], {zoom});

        // Добавляем слой 2GIS (лучший для России)
        L.tileLayer('https://tile2.maps.2gis.com/tiles?x={{x}}&y={{y}}&z={{z}}&v=1', {{
            maxZoom: 18
        }}).addTo(map);

        // Данные зеленых зон
        var zones = {json.dumps(valid_zones, ensure_ascii=False)};

        console.log('🗺️ Zones loaded:', zones);

        // Создаем маркеры для каждой зоны
        zones.forEach(function(zone) {{
            // Определяем цвет иконки в зависимости от состояния
            var iconColor;
            if (zone.health_score >= 80) {{
                iconColor = 'green';
            }} else if (zone.health_score >= 60) {{
                iconColor = 'orange';
            }} else {{
                iconColor = 'red';
            }}

            // Создаем кастомную иконку
            var greenIcon = new L.Icon({{
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-' + iconColor + '.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            }});

            // Создаем маркер
            var marker = L.marker([zone.lat, zone.lon], {{icon: greenIcon}}).addTo(map);

            // Создаем содержимое popup
            var popupContent = `
                <div style="min-width: 250px;">
                    <h5 style="margin: 0 0 10px 0; color: #2c3e50;">
                        <i class="fas fa-tree"></i> ${{zone.name}}
                    </h5>
                    <p><strong>Тип:</strong> ${{zone.zone_type}}</p>
                    <p><strong>Площадь:</strong> ${{zone.area}} га</p>
                    <p><strong>Состояние:</strong> 
                        <span style="color: ${{iconColor}}; font-weight: bold;">
                            ${{zone.health_score.toFixed(1)}}%
                        </span>
                    </p>
                    <p><strong>Задачи:</strong> ${{zone.pending_tasks}}</p>
                    <p><strong>Местоположение:</strong> ${{zone.location}}</p>
                    <a href="/zone/${{zone.id}}" class="btn btn-sm btn-primary w-100" style="margin-top: 10px;">
                        <i class="fas fa-external-link-alt me-1"></i>Перейти к зоне
                    </a>
                </div>
            `;

            // Привязываем popup к маркеру
            marker.bindPopup(popupContent);

            // Добавляем обработчик клика
            marker.on('click', function() {{
                this.openPopup();
            }});
        }});

        // Добавляем легенду
        var legend = L.control({{position: 'bottomright'}});
        legend.onAdd = function (map) {{
            var div = L.DomUtil.create('div', 'legend');
            div.style.backgroundColor = 'white';
            div.style.padding = '10px';
            div.style.borderRadius = '5px';
            div.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
            div.innerHTML = `
                <h5 style="margin: 0 0 8px 0; font-size: 14px;">
                    <i class="fas fa-tree"></i> Состояние зон
                </h5>
                <div style="margin-bottom: 5px;">
                    <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png" style="width: 12px; height: 20px; display: inline-block; margin-right: 5px;">
                    Отлично (80-100%)
                </div>
                <div style="margin-bottom: 5px;">
                    <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png" style="width: 12px; height: 20px; display: inline-block; margin-right: 5px;">
                    Хорошо (60-79%)
                </div>
                <div>
                    <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png" style="width: 12px; height: 20px; display: inline-block; margin-right: 5px;">
                    Требует внимания (<60%)
                </div>
            `;
            return div;
        }};
        legend.addTo(map);

        // Добавляем масштаб
        L.control.scale({{imperial: false}}).addTo(map);
    </script>
    '''

    return map_html


# Сохраняем старые функции для обратной совместимости
class MapService:
    generate_simple_map = generate_map_with_zones

    @staticmethod
    def generate_leaflet_map(zones, tile_provider='2gis'):
        """Генерация полноэкранной карты с выбором провайдера"""

        # Фильтруем зоны с валидными координатами
        valid_zones = []
        for zone in zones:
            coords = zone.get('coordinates')
            if coords:
                try:
                    coords_clean = coords.strip().replace(' ', '')
                    if ',' in coords_clean:
                        lat_str, lon_str = coords_clean.split(',')
                        lat, lon = float(lat_str), float(lon_str)
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            valid_zones.append({
                                'id': zone['id'],
                                'name': zone['name'],
                                'lat': lat,
                                'lon': lon,
                                'health_score': zone.get('avg_health', 0) or 0
                            })
                except:
                    continue

        # Определяем центр карты
        if valid_zones:
            center_lat = sum(z['lat'] for z in valid_zones) / len(valid_zones)
            center_lon = sum(z['lon'] for z in valid_zones) / len(valid_zones)
            zoom = 12
        else:
            center_lat, center_lon = 55.7558, 37.6173
            zoom = 5

        # Определяем тайловый слой в зависимости от провайдера
        tile_layers = {
            '2gis': {
                'url': 'https://tile2.maps.2gis.com/tiles?x={x}&y={y}&z={z}&v=1',
                'maxZoom': 18
            },
            'openstreetmap': {
                'url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                'maxZoom': 18
            },
            'cartodb': {
                'url': 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
                'maxZoom': 18
            },
            'opentopomap': {
                'url': 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
                'maxZoom': 17
            },
            'cyclosm': {
                'url': 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png',
                'maxZoom': 18
            }
        }

        tile_config = tile_layers.get(tile_provider, tile_layers['2gis'])

        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Карта зеленых зон</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <style>
                body {{ margin: 0; padding: 0; }}
                #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
                .legend {{
                    background: white;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>

            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script>
                // Инициализация карты с отключенной атрибуцией
                var map = L.map('map', {{
                    attributionControl: false
                }}).setView([{center_lat}, {center_lon}], {zoom});

                // Добавляем выбранный тайловый слой
                L.tileLayer('{tile_config["url"]}', {{
                    maxZoom: {tile_config["maxZoom"]}
                }}).addTo(map);

                // Добавляем зоны
                var zones = {json.dumps(valid_zones, ensure_ascii=False)};

                zones.forEach(function(zone) {{
                    var iconColor = zone.health_score >= 80 ? 'green' : zone.health_score >= 60 ? 'orange' : 'red';

                    var greenIcon = new L.Icon({{
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-' + iconColor + '.png',
                        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41],
                        popupAnchor: [1, -34],
                        shadowSize: [41, 41]
                    }});

                    var marker = L.marker([zone.lat, zone.lon], {{icon: greenIcon}}).addTo(map);

                    var popupContent = `
                        <div style="min-width: 250px;">
                            <h5 style="margin: 0 0 10px 0; color: #2c3e50;">
                                <i class="fas fa-tree"></i> ${{zone.name}}
                            </h5>
                            <p><strong>Состояние:</strong> 
                                <span style="color: ${{iconColor}}; font-weight: bold;">
                                    ${{zone.health_score.toFixed(1)}}%
                                </span>
                            </p>
                            <a href="/zone/${{zone.id}}" target="_blank" class="btn btn-sm btn-primary" style="margin-top: 10px;">
                                Перейти к зоне
                            </a>
                        </div>
                    `;

                    marker.bindPopup(popupContent);
                }});

                // Добавляем легенду
                var legend = L.control({{position: 'bottomright'}});
                legend.onAdd = function (map) {{
                    var div = L.DomUtil.create('div', 'legend');
                    div.innerHTML = `
                        <div style="padding: 10px;">
                            <h5 style="margin: 0 0 8px 0; font-size: 14px;">Состояние зон</h5>
                            <div style="margin-bottom: 5px;">
                                <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png" style="width: 12px; height: 20px; display: inline-block; margin-right: 5px;">
                                Отлично (80-100%)
                            </div>
                            <div style="margin-bottom: 5px;">
                                <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png" style="width: 12px; height: 20px; display: inline-block; margin-right: 5px;">
                                Хорошо (60-79%)
                            </div>
                            <div>
                                <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png" style="width: 12px; height: 20px; display: inline-block; margin-right: 5px;">
                                Требует внимания (<60%)
                            </div>
                        </div>
                    `;
                    return div;
                }};
                legend.addTo(map);

                // Добавляем масштаб
                L.control.scale({{imperial: false}}).addTo(map);
            </script>
        </body>
        </html>
        '''

        return html

    @staticmethod
    def get_nominatim_coordinates(city_name):
        """Получить координаты города через Nominatim"""
        try:
            import requests
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': f'{city_name}, Россия',
                'format': 'json',
                'limit': 1
            }
            headers = {'User-Agent': 'GreenCityPlatform/1.0'}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data:
                    return {
                        'lat': float(data[0]['lat']),
                        'lon': float(data[0]['lon'])
                    }
            return None
        except Exception as e:
            print(f"Error getting coordinates: {e}")
            return None

    @staticmethod
    def reverse_geocode(lat, lon):
        """Обратное геокодирование - получение адреса по координатам"""
        try:
            import requests
            import time
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'zoom': 18,
                'addressdetails': 1
            }
            headers = {
                'User-Agent': 'GreenCityPlatform/1.0',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'
            }

            time.sleep(1)

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and 'display_name' in data:
                    return data['display_name']
            return None
        except Exception as e:
            print(f"Error reverse geocoding: {e}")
            return None