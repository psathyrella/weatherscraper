#!/usr/bin/env python

import requests
import datetime
from bs4 import BeautifulSoup

# features
#  - image, temp, wind, expected precip
#  - also show last three days or so, especially precip, wind, temp
#  - current snow pack (?)

weekdays = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

locations = {
    # 'stuart' : (47.48, -120.90),
    'hozomean-camp' : (48.82, -121.34)
}

# http://forecast.weather.gov/MapClick.php?textField1=47.48&textField2=-120.90
# url = 'http://forecast.weather.gov/MapClick.php?textField1=' + 47.4 + '&textField2=-120.90'
baseurl = 'http://forecast.weather.gov/afm'
for name in locations:
    lat = locations[name][0]
    lon = locations[name][1]
    url = baseurl + '/PointClick.php?lat=' + str(lat) + '&lon=' + str(lon)
    # bs = BeautifulSoup(requests.get(url).text)  #, from_encoding='utf-8')
    bs = BeautifulSoup(open('example.html'))
    dates = bs.find_all('div', {'class':'date'})
    days = bs.find_all('div', {'class':'day'})
    for d in days:
        print d
    # print bs.prettify()
    # txt = bs.decode(pretty_print=True)
    # with open('tmp.html', 'w') as outfile:
    #     outfile.write(txt)
