import csv
data = {}
with open('city.csv') as csvfile:
    reader = csv.DictReader(csvfile, delimiter=';', quotechar='"')
    for city in reader:
        data[city['name'][0].lower()] = data.get(city['name'][0].lower(), []) + [city['name']]
import json
print(data)
with open('cities.json',mode = 'w', encoding='utf-8') as f:
    f.write(json.dumps(data, ensure_ascii=False))