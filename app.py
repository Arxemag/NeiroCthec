from suds.client import Client
from suds.transport.http import HttpAuthenticated


# ======================
# КЛАССЫ УСЛОВИЙ ПОИСКА
# ======================

# ======================
# Классы условий поиска
# Класс для условий поиска строкового типа
class SearchConditionString:
    def __init__(self, id, value):
        self.id = id
        self.value = value

# Класс для условий поиска числового типа
class SearchConditionNumber:
    def __init__(self, id, value, mode):
        self.id = id
        self.value = value
        self.mode = mode

# Класс для условий поиска даты
class SearchConditionDate:
    def __init__(self, id, values, mode):
        self.id = id
        self.values = values
        self.mode = mode

# Класс для условий поиска классификатора
class SearchConditionClassificator:
    def __init__(self, id, values, lop):
        self.id = id
        self.values = values
        self.lop = lop

# ======================
# НАСТРОЙКИ
# ======================

wsdl = "http://suntd.kodeks.expert:7070/docs/api?wsdl&use=encoded"

LOGIN = "kodeks"
PASSWORD = "skedoks"

search_text = ("гост 123")


# ======================
# SOAP КЛИЕНТ (SUDS)
# ======================

transport = HttpAuthenticated(username=LOGIN, password=PASSWORD)
kodweb = Client(wsdl, transport=transport)




# Выполнение поиска атрибутов
# Создание объекта условия поиска по атрибуту, от функиции зависит по какому атрибуту будет идти поиск SearchConditionString - Наименование; SearchConditionNumber - Номер документа; SearchConditionDate - Дата; SearchConditionClassificator - классификатор(Нужно передать ND классификатора по которому будем искать)
serc_atr = kodweb.service.AttrSearch(SearchConditionString(0, search_text), "", -1)
print(serc_atr)
# Получение списка атрибутов для поиска
atribut = kodweb.service.GetSearchListOrders(serc_atr.id,'')
# Вывод списка атрибутов
print(atribut)


# Получение списка документов
# Получение списка документов на основе атрибутов поиска
documents = kodweb.service.GetSearchListN(serc_atr.id, atribut.item_OrderListItem[0], 0, '', 0, False)


# Вывод списка документов
print(documents.item_DocListItem)
# Обратный порядок документов
# Переворот списка документов
reversed_documents = documents.item_DocListItem[::-1]
# Вывод списка документов
print(documents.item_DocListItem)
# Вывод перевернутого списка документов
print(reversed_documents)
