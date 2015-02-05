#!/usr/bin/env python
import csv
import argparse
import os
import datetime
from xml.etree import ElementTree as ET
import urllib

import HTML
import ndfdparser
import htmlinfo

parser = argparse.ArgumentParser()
parser.add_argument('--location-fname', default='all-locations.csv')
parser.add_argument('--outfname', required=True)
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
    forecast = ndfdparser.forecast(tree, htmldir=os.path.dirname(os.path.abspath(args.outfname)))
    return forecast

# ----------------------------------------------------------------------------------------
rows = []
with open(args.location_fname) as location_file:
    reader = csv.DictReader(location_file)
    for line in reader:
        print '\n%s:' % line['name']
        args.location = ()
        days, forecast = get_forecast(args, line['lat'], line['lon'])
        forecast[0] = forecast[0].replace('LOCATION</a>', line['name'] + '</a><br>' + line['elevation'] + ' ft')
        rows.append(forecast)

htmlcode = HTML.table(rows, header_row=['location<br>(forecast elevation)',] + days)
if not os.path.exists:
    os.makedirs('_html')
with open(args.outfname, 'w') as outfile:
    outfile.write('retreived: ' + str(datetime.datetime.now()) + '\n')
    outfile.write(htmlinfo.headtext)
    outfile.write(htmlcode)
