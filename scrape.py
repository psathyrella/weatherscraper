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
    # print url
    resp = urllib.urlopen(url)
    tree = ET.parse(resp)
    forecast = ndfdparser.forecast(tree, htmldir=os.path.dirname(os.path.abspath(args.outfname)))
    return forecast

# ----------------------------------------------------------------------------------------
# get forecast for each location
rows = []
with open(args.location_fname) as location_file:
    reader = csv.DictReader(filter(lambda row: row[0]!='#', location_file))
    for line in reader:
        print '\n%s:' % line['name']
        args.location = ()
        days, forecast = get_forecast(args, line['lat'], line['lon'])
        forecast[0] = forecast[0].replace('LOCATION</a>', line['name'] + '</a><br>' + line['elevation'] + ' ft')
        rows.append(forecast)

# write html output
htmlcode = HTML.table(rows, header_row=['location<br>(approx. elevation)',] + days)
if not os.path.exists:
    os.makedirs('_html')
with open(args.outfname, 'w') as outfile:
    outfile.write('retreived %s\n' % datetime.datetime.now().strftime('%B %d %Y at %H:%M'))
    outfile.write(htmlinfo.headtext)
    outfile.write(htmlcode)

    sundries = []
    sundries.append(['<a href="http://www.mountain-forecast.com/peaks/Mount-Waddington/forecasts/3500">Mt Waddington</a>', ])
    sundries.append(['<a href="http://weather.gc.ca/city/pages/bc-50_metric_e.html">Squamish</a>', ])
    outfile.write(HTML.table(sundries, header_row=['<b>sundries</b><br>', ]))
    outfile.write('<br><br><a href=\"https://github.com/psathyrella/weatherscraper\">github</a>\n')
    
