import json
from flask import Flask, request
import logging
import requests

# change to this and print city that lasts on 'a' to see Alisa lose
#            V
# with open('/home/Dmitry315/mysite/cities_to_show_win.json', mode='r', encoding='utf-8') as f:
with open('/home/Dmitry315/mysite/cities.json', mode='r', encoding='utf-8') as f:
    CitiesBase = json.load(f)

# init Flask
app = Flask(__name__)

# add logging
logging.basicConfig(level=logging.INFO, filename='app.log', format='%(asctime)s %(levelname)s %(name)s %(message)s')
# Yandex geocoder server to check city
GeoCode = 'http://geocode-maps.yandex.ru/1.x/'
API_KEY = 'dda3ddba-c9ea-4ead-9010-f43fbc15c6e3'
# save information about users in session
sessionStorage = {}


# main
@app.route('/post', methods=['POST'])
def index():
    logging.info('Request: %r', request.json)
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }
    handle_dialog(response, request.json)

    logging.info('Request: %r', response)

    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']

    # get there if user starts dialog
    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        res['response']['buttons'] = []
        sessionStorage[user_id] = {
            'first_name': None,
            'game_started': False,
            'called_cities': []
        }
        return
    # git there if user didn't said his name
    if not sessionStorage[user_id]['first_name']:
        name = get_first_name(req)
        if name:
            res['response']['text'] = f'Привет, {name.title()}! Сыграем в города?'
            res['response']['buttons'] = [
                {
                    'title': 'Да',
                    'hide': True
                },
                {
                    'title': 'Нет',
                    'hide': True
                },
                {
                    'title': 'Расскажи правила',
                    'hide': True
                }
            ]
            sessionStorage[user_id]['first_name'] = name.title()
        # get there is no name in answer
        else:
            res['response']['text'] = 'Не расслышала. Повтори, пожалуйста!'
        return
    # help for user
    if req['request']['original_utterance'].lower() in ['помощь', 'расскажи правила']:
        res['response']['text'] = '''Один игрок начинает с любого города.
        Следующий игрок называет город, начинающийся с буквы, на которую заканчивается этот город.
        Затем другой игрок называет город, начинающийся с буквы, на которую заканчивается предыдущий город
        И так далее. Я могу подсказать вам 3 раза. Желательно писать просто название города.
        Когда попадаются города, оканчивающиеся на "ь" или "ы" то нужно назвать город,
        оканчивающийся на предпоследнюю букву.'''
        if not sessionStorage[user_id]['game_started']:
            res['response']['buttons'] = [
                {
                    'title': 'Да',
                    'hide': True
                },
                {
                    'title': 'Нет',
                    'hide': True
                }]
        else:
            res['response']['buttons'] = [
                {
                    'title': 'Подсказка (' + str(sessionStorage[user_id]['hints']) + ')',
                    'hide': True
                }]
        return
    # show city to user
    if sessionStorage[user_id]['game_started'] and req['request']['original_utterance'].lower() == 'где этот город?':
        res['response']['text'] = 'Город можно посмотреть на Яндекс картах!'
        res['response']['buttons'] = [
            {
                'title': 'Помощь',
                'hide': True,
            },
            {
                'title': 'Подсказка (' + str(sessionStorage[user_id]['hints']) + ')',
                'hide': True
            },
            {
                'title': 'Сдаюсь',
                'hide': True
            },
        ]
        return
    # continue game
    if sessionStorage[user_id]['game_started']:
        play_game(res, req)
        return
    # game start
    if req['request']['original_utterance'].lower() in ['да', 'ладно', 'хорошо', 'ок', 'ok']:
        res['response']['text'] = 'Хорошо, начинай!'
        sessionStorage[user_id]['game_started'] = True
        sessionStorage[user_id]['called_cities'] = []
        sessionStorage[user_id]['hints'] = 3
        res['response']['buttons'] = [
            {
                'title': 'Помощь',
                'hide': True,
            },
            {
                'title': 'Подсказка (' + str(sessionStorage[user_id]['hints']) + ')',
                'hide': True
            },
        ]
        return
    # reject
    if req['request']['original_utterance'].lower() in ['нет', 'в следующий раз', 'потом']:
        res['response']['text'] = 'Ну и ладно!'
        res['response']['end_session'] = True
        return
    # if something gone wrong
    else:
        res['response']['text'] = 'Не расслышала. Повтори, пожалуйста!'
        return


# game cycle
def play_game(res, req):
    user_id = req['session']['user_id']
    res['response']['buttons'] = [
        {
            'title': 'Помощь',
            'hide': True,
        },
        {
            'title': 'Подсказка (' + str(sessionStorage[user_id]['hints']) + ')',
            'hide': True
        },
        {
            'title': 'Сдаюсь',
            'hide': True
        },
    ]
    # user's move
    city = get_city(req)
    # user surrender
    if req['request']['original_utterance'].lower() in ['я проиграл', 'я сдаюсь', 'ты победила', 'ты выиграла',
                                                        'сдаюсь']:
        res['response']['text'] = 'В следующий раз ты обязательно победишь. Сыграем ещё?'
        sessionStorage[user_id]['game_started'] = False
        res['response']['buttons'] = [
            {
                'title': 'Да',
                'hide': True
            },
            {
                'title': 'Нет',
                'hide': True
            }]
        # delete list of cities for the next game
        sessionStorage[user_id]['cities'] = []
        return
    # user use hint
    if req['request']['original_utterance'].lower() in ['подсказка (3)', 'подсказка (2)', 'подсказка (1)',
                                                        'подсказка (0)', 'дай подсказку', 'подскажи']:
        # user has no hints
        if sessionStorage[user_id]['hints'] < 1:
            res['response']['text'] = 'У вас больше не осталось подсказок'
        # users unique chance to lose hints before game started :)
        elif not sessionStorage[user_id]['called_cities']:
            res['response']['text'] = 'Хорошо, предлагаю город Москва.'
            sessionStorage[user_id]['hints'] -= 1
        else:
            litter = sessionStorage[user_id]['called_cities'][-1][-1]
            litter = sessionStorage[user_id]['called_cities'][-1][-2] if litter in ['ъ', 'ь', 'ы'] else litter
            res['response']['text'] = sessionStorage[user_id]['called_cities'][-1]
            hinted_city = get_city_by_litter(litter, user_id)
            if hinted_city:
                res['response']['text'] = f'Хорошо, предлагаю город {hinted_city}.'
                sessionStorage[user_id]['hints'] -= 1
            # Alisa doesn't know, but it doesn't mean that there is no such city
            else:
                res['response']['text'] = 'Извини, я не знаю.'
        res['response']['buttons'] = [
            {
                'title': 'Помощь',
                'hide': True,
            },
            {
                'title': 'Подсказка (' + str(sessionStorage[user_id]['hints']) + ')',
                'hide': True
            },
            {
                'title': 'Сдаюсь',
                'hide': True
            },
        ]
        return
    # check with geocoder if there is no such city in data base
    if not city:
        if check_city(req):
            city = req['request']['original_utterance'].lower()
    # if there is no such city in geocoder
    if not city:
        res['response']['text'] = 'Я не знаю такого города, попробуй другой'
        return
    # if user repeat city
    if city in sessionStorage[user_id]['called_cities']:
        res['response']['text'] = 'Этот город уже был! Назови другой.'
        return
    # if session is empty
    elif not sessionStorage[user_id]['called_cities']:
        sessionStorage[user_id]['called_cities'].append(city.lower())
    # check that city starts with litter on which last city lasts
    elif not ((city[0].lower() == sessionStorage[user_id]['called_cities'][-1][-2].lower() and
                       sessionStorage[user_id]['called_cities'][-1][-1].lower() in ['ъ', 'ь', 'ы']) or city[
        0].lower() == sessionStorage[user_id]['called_cities'][-1][-1].lower()):
        litter = sessionStorage[user_id]['called_cities'][-1][-1]
        litter = sessionStorage[user_id]['called_cities'][-1][-2] if litter in ['ъ', 'ь', 'ы'] else litter
        res['response']['text'] = f'Нет, тебе на "{litter}".'
        return
    else:
        sessionStorage[user_id]['called_cities'].append(city.lower())
    # Alisa's move
    litter = sessionStorage[user_id]['called_cities'][-1][-1]
    # except litter on which city can't lasts
    litter = sessionStorage[user_id]['called_cities'][-1][-2] if litter in ['ъ', 'ь', 'ы'] else litter
    alisa_city = get_city_by_litter(litter, user_id)
    if alisa_city:
        last_litter = alisa_city[-2] if alisa_city[-1] in ['ъ', 'ь', 'ы'] else alisa_city[-1]
        res['response']['text'] = f'{alisa_city}, тебе на "{last_litter}"'
        sessionStorage[user_id]['called_cities'].append(alisa_city.lower())
        # show user link on this city
        res['response']['buttons'].append({
            'title': 'Где этот город?',
            'url': 'https://yandex.ru/maps/?mode=search&text=' + alisa_city.replace(' ', '+'),
            'hide': True
        })
    # Alisa lose and game stops
    else:
        res['response']['text'] = 'Я сдаюсь. Сыграем ещё?'
        res['response']['buttons'] = [
            {
                'title': 'Да',
                'hide': True
            },
            {
                'title': 'Нет',
                'hide': True
            }]
        sessionStorage[user_id]['game_started'] = False
        sessionStorage[user_id]['called_cities'] = []
        return


# search in data base for a city that lasts on some litter
def get_city_by_litter(litter, user_id):
    available = CitiesBase[litter]
    for city in available:
        if city.lower() not in sessionStorage[user_id]['called_cities']:
            return city
    return False


# check city with geocoder
def check_city(req):
    try:
        city = req['request']['original_utterance']
        params = {
            'geocode': city,
            'format': 'json',
        }
        response = requests.get(GeoCode, params=params).json()
        toponym = response["response"]["GeoObjectCollection"]["featureMember"]
        return bool(toponym)
    except Exception as err:
        return False


# pull first name from request (None if it doesn't find)
def get_first_name(req):
    # перебираем сущности
    for entity in req['request']['nlu']['entities']:
        # находим сущность с типом 'YANDEX.FIO'
        if entity['type'] == 'YANDEX.FIO':
            # Если есть сущность с ключом 'first_name', то возвращаем её значение.
            # Во всех остальных случаях возвращаем None.
            return entity['value'].get('first_name', None)


# pull city name from request (None if it doesn't find)
def get_city(req):
    # перебираем именованные сущности
    for entity in req['request']['nlu']['entities']:
        # если тип YANDEX.GEO, то пытаемся получить город(city), если нет, то возвращаем None
        if entity['type'] == 'YANDEX.GEO':
            # возвращаем None, если не нашли сущности с типом YANDEX.GEO
            return entity['value'].get('city', None)


if __name__ == '__main__':
    app.run()
