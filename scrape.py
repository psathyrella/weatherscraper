#!/usr/bin/env python
import csv
import argparse
import os
import datetime
from xml.etree import ElementTree as ET
from lxml import etree
import urllib
import sys

import HTML
import ndfdparser
import mtwxparser
import htmlinfo

parser = argparse.ArgumentParser()
parser.add_argument('--location-fname', default='all-locations.csv')
parser.add_argument('--outfname', required=True)
parser.add_argument('--no-history', action='store_true', help='Don\'t add a column with history plot (still caches current forecast even if true)')
args = parser.parse_args()

# ----------------------------------------------------------------------------------------
def get_mtf_link(location, elevation):
    return 'http://www.mountain-forecast.com/peaks/' + location + '/forecasts/' + str(elevation)

# ----------------------------------------------------------------------------------------
def get_forecast(args, location_name, lat, lon, mtwx_location=None, mtwx_elevation=None, start_date=datetime.date.today(), num_days=6, metric=False):
    if mtwx_location is None:
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
        forecast = ndfdparser.forecast(args, tree, location_name, htmldir=os.path.dirname(os.path.abspath(args.outfname)))
        return forecast
    else:
        # url = get_mtf_link(mtwx_location, mtwx_elevation)
        parser = etree.HTMLParser()
        # tree = etree.parse(url, parser)
        tree = etree.parse('tmp.html', parser)
        forecast = mtwxparser.forecast(args, tree, num_days=num_days)

# ----------------------------------------------------------------------------------------
# get forecast for each location
rows = []
fails = []
with open(args.location_fname) as location_file:
    reader = csv.DictReader(filter(lambda row: row[0]!='#', location_file))
    for line in reader:
        print '\n%s:' % line['name']
        args.location = ()
        n_tries = 0
        # while n_tries < 3:
        days, forecast = get_forecast(args, line['name'], line['lat'], line['lon'], line['mtwx-location'], line['mtwx-elevation'])
        try:
            days, forecast = get_forecast(args, line['name'], line['lat'], line['lon'], line['mtwx-location'], line['mtwx-elevation'])
            extrastr = line['name'] + '<br>'
            extrastr += '<font size="2">' + line['elevation'] + ' ft <br></font>'
            if line['mtwx-location'] != '':
                extrastr += '<font size="2"><a href="' + get_mtf_link(line['mtwx-location'], line['mtwx-elevation']) + '">mtfcast</a></font>'
            forecast[0] = forecast[0].replace('LOCATION', extrastr)
            rows.append(forecast)
            # break
        except AttributeError:
            fails.append(line['name'])
        n_tries += 1

# write html output
header = ['location<br>(<a href="https://github.com/psathyrella/weatherscraper/issues/5">approx.</a> elevation)', ]
if not args.no_history:
    header.append('history')
htmlcode = HTML.table(rows, header_row=header + days)
if not os.path.exists:
    os.makedirs('_html')
with open(args.outfname, 'w') as outfile:
    outfile.write('retrieved %s<br>' % datetime.datetime.now().strftime('%a %B %d %Y at %H:%M'))
    tmpdatestr = datetime.datetime.now().strftime('%Y%m%d12')
    outfile.write('<a href="http://www.atmos.washington.edu/~ovens/wxloop.cgi?/home/disk/data/images/models+all+-pat+%28eta|gfs|ngps|cmcg|ukmo|ecmwf%29/pcpn_slp_thkn/' + tmpdatestr + '_***.gif+-update+3600">overview</a>\n')
    outfile.write(htmlinfo.headtext)
    outfile.write(htmlcode)

    sundries = []
    sundries.append(['<a href="' + get_mtf_link('Mount-Waddington', 4016) + '">Waddington</a>', ])
    sundries.append(['<a href="' + get_mtf_link('Slesse-Peak', 2393) + '">Slesse</a>', ])
    sundries.append(['<a href="' + get_mtf_link('Serratus-Mountain', 2321) + '">Serratus</a>', ])
    sundries.append(['<a href="http://weather.gc.ca/city/pages/bc-50_metric_e.html">Squamish</a>', ])
    outfile.write(HTML.table(sundries, header_row=['<b>sundries</b><br>', ]))
    if not args.no_history:
        outfile.write('<br>Note: "history" is the point forecast archived the day before, i.e. somewhat less than 24 hours in advance, of the indicated date.<br>')
    outfile.write('<br><br><a href=\"https://github.com/psathyrella/weatherscraper\">github</a><br><br>')
    if len(fails) > 0:
        outfile.write('wget failed (ndfd server getting ddos\'d?) for:<br>')
        outfile.write('<br>'.join(fails))
