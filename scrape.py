#!/usr/bin/env python
import csv
import argparse
import os
import datetime
from xml.etree import ElementTree as ET
import urllib

import ndfdparser
import htmlinfo

parser = argparse.ArgumentParser()
parser.add_argument('--location-fname', default='all-locations.csv')
args = parser.parse_args()

# ----------------------------------------------------------------------------------------
def get_forecast(args, lat, lon, start_date=datetime.date.today(), num_days=6, metric=False):
    location_info = [('lat', lat), ('lon', lon)]
    params = location_info + [("format", "24 hourly"),
                              ("startDate", start_date.strftime("%Y-%m-%d")),
                              ("numDays", str(num_days)),
                              ("Unit", "m" if metric else "e")]
    query_string = urllib.urlencode(params)
    client_type = 'XMLclient'
    FORECAST_BY_DAY_URL = ("http://www.weather.gov/forecasts/xml"
                           "/sample_products/browser_interface"
                           "/ndfd" + client_type + ".php")
    
    url = "?".join([FORECAST_BY_DAY_URL, query_string])
    resp = urllib.urlopen(url)
    tree = ET.parse(resp)
    forecast = ndfdparser.forecast(tree)
    return forecast

# ----------------------------------------------------------------------------------------
htmlcode = ''
with open(args.location_fname) as location_file:
    reader = csv.DictReader(location_file)
    for line in reader:
        print '\n%s:' % line['name']
        args.location = ()
        forecast = get_forecast(args, line['lat'], line['lon'])
        htmlcode += forecast.replace('LOCATION</a>', line['name'] + '</a><br>' + line['elevation'])

if not os.path.exists:
    os.makedirs('_html')
with open('_html/tmp.html', 'w') as outfile:
    outfile.write(str(datetime.datetime.now()) + '\n')
    outfile.write(htmlinfo.headtext)
    outfile.write(htmlcode)
