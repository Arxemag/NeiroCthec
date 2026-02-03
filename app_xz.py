from flask import Flask, request, jsonify
from suds.client import Client
from suds.transport.http import HttpAuthenticated


app = Flask(__name__)

# Настройки
LOGIN = "kodeks"
PASSWORD = "skedoks"
WSDL_URL = "http://suntd.kodeks.expert:7070/docs/api?wsdl&use=encoded"


# Создаём клиент
transport = HttpAuthenticated(username=LOGIN, password=PASSWORD)
try:
    client = Client(WSDL_URL, transport=transport)
    print("✅ Подключение к Kodweb установлено")
except Exception as e:
    print("❌ Ошибка подключения:", str(e))
    client = None


# Классы условий (обязательно!)
class SearchConditionString:
    def __init__(self, id, value):
        self.id = id
        self.value = value


@app.route("/api/fuzzy_search", methods=["POST"])
def fuzzy_search():
    if not client:
        return jsonify({"documents": [], "error": "No client"}), 500

    data = request.json
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"documents": []})

    try:
        print("\n" + "="*60)
        print("🔍 НОВЫЙ ЗАПРОС")
        print(f"📝 Запрос: '{query}'")
        print("="*60)

        # === AttrSearch ===
        print("\n1️⃣ Выполняем AttrSearch...")
        result_attr = client.service.AttrSearch(
            SearchConditionString(0, query),
            "",
            -1
        )

        print(f"✅ AttrSearch успешен")
        print(f"📍 Тип result_attr: {type(result_attr)}")
        print(f"📋 Содержимое result_attr: {result_attr}")
        print(f"🔗 list_id: {result_attr.id}")

        list_id = result_attr.id

        # === GetSearchListOrders ===
        print("\n2️⃣ Получаем GetSearchListOrders...")
        orders = client.service.GetSearchListOrders(list_id, '')

        print(f"✅ GetSearchListOrders успешен")
        print(f"📍 Тип orders: {type(orders)}")
        print(f"📋 Содержимое orders: {orders}")

        if not hasattr(orders, 'item_OrderListItem') or not orders.item_OrderListItem:
            print("❌ Нет item_OrderListItem в ответе")
            return jsonify({"documents": [], "error": "No order items"}), 500

        order_item = orders.item_OrderListItem[0]
        print(f"\n🎯 Используем первый order_item:")
        print(f"📍 Тип order_item: {type(order_item)}")
        print(f"📋 Содержимое order_item: {order_item}")

        # === GetSearchListN ===
        print("\n3️⃣ Выполняем GetSearchListN...")
        documents_result = client.service.GetSearchListN(
            list_id,
            None,
            0, '', '0', False
        )

        print(f"✅ GetSearchListN успешен")
        print(f"📍 Тип documents_result: {type(documents_result)}")
        print(f"📋 Содержимое documents_result: {documents_result}")

        # 🔧 Извлечение массива документов
        if isinstance(documents_result, tuple):
            print("🟡 documents_result — это tuple, берём [0]")
            raw_items = documents_result[0] if len(documents_result) > 0 else []
        elif hasattr(documents_result, 'item_DocListItem'):
            print("🟢 documents_result имеет item_DocListItem")
            raw_items = documents_result.item_DocListItem
        elif hasattr(documents_result, '_value_1'):
            print("🔵 documents_result имеет _value_1")
            raw_items = documents_result._value_1
        else:
            print("🔴 Неизвестная структура documents_result")
            print("🔧 Попробуем использовать как есть")
            raw_items = documents_result

        print(f"\n4️⃣ Извлечение списка документов")
        print(f"📍 Тип raw_items: {type(raw_items)}")
        print(f"📋 Содержимое raw_items: {raw_items}")

        # Приведение к списку
        if isinstance(raw_items, dict):
            items = [raw_items]
        elif isinstance(raw_items, (list, tuple)):
            items = list(raw_items)
        else:
            items = [raw_items] if raw_items else []

        print(f"📄 Финальный список документов: {len(items)} шт.")
        for i, item in enumerate(items):
            print(f"\n--- 📄 Документ {i+1} ---")
            print(f"📍 Тип: {type(item)}")
            print(f"📋 Сырое содержимое: {item}")

            # Извлекаем поля
            if isinstance(item, dict):
                nd = item.get('nd', 'Без ND')
                name = item.get('name', 'Без названия')
                info = item.get('info', 'Нет аннотации')
                haskdoc = item.get('haskdoc', False)
            else:
                nd = getattr(item, 'nd', 'Без ND')
                name = getattr(item, 'name', 'Без названия')
                info = getattr(item, 'info', 'Нет аннотации')
                haskdoc = getattr(item, 'haskdoc', False)

            print(f"ND:         {nd}")
            print(f"Название: {name}")
            print(f"Аннотация: {info}")
            print(f"Есть текст: {'Да' if haskdoc else 'Нет'}")

        # Формируем JSON-ответ
        docs = []
        for item in items:
            if isinstance(item, dict):
                nd = item.get('nd', 'Без ND')
                name = item.get('name', 'Без названия')
                info = item.get('info', 'Нет аннотации')
                haskdoc = item.get('haskdoc', False)
            else:
                nd = getattr(item, 'nd', 'Без ND')
                name = getattr(item, 'name', 'Без названия')
                info = getattr(item, 'info', 'Нет аннотации')
                haskdoc = getattr(item, 'haskdoc', False)

            docs.append({
                "nd": str(nd),
                "title": str(name),
                "summary": str(info),
                "url": f"http://suntd.kodeks.expert:7070/docs/doc/{nd}",
                "has_text": bool(haskdoc)
            })

        print(f"\n✅ Ответ сформирован: {len(docs)} документов")
        return jsonify({"documents": docs, "list_id": list_id})

    except Exception as e:
        print(f"\n❌ Ошибка в fuzzy_search: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"documents": [], "error": str(e)}), 500




@app.route("/")
def index():
    return '''
    <h1>API Готов</h1>
    <p>Отправь POST-запрос на <code>/api/fuzzy_search</code></p>
    <pre>
curl -X POST http://localhost:5000/api/fuzzy_search \\
     -H "Content-Type: application/json" \\
     -d '{"query": "гражданский кодекс"}'
    </pre>
    '''


if __name__ == "__main__":
    app.run(debug=True)