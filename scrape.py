#!/usr/bin/env python
import csv
import argparse
import os
import datetime
from xml.etree import ElementTree as ET
from collections import OrderedDict
from lxml import etree
import urllib
import sys

import HTML
import ndfdparser
import mtwxparser
import htmlinfo

parser = argparse.ArgumentParser()
parser.add_argument('--location-fname', default='all-locations.csv')
parser.add_argument('--noaa-location-fname', default='locations/noaa.csv')
parser.add_argument('--mtwx-location-fname', default='locations/mtwx.csv')
parser.add_argument('--outfname', required=True)
parser.add_argument('--history-dir', default='_history')
parser.add_argument('--cachedir', default='_cache')
parser.add_argument('--no-history', action='store_true', help='Don\'t add a column with history plot (still caches current forecast even if true)')
parser.add_argument('--old-style', action='store_true')
parser.add_argument('--use-cache', action='store_true', help='read from cached html/xml files')
args = parser.parse_args()

if not os.path.exists(os.path.dirname(args.outfname)):
    os.makedirs(os.path.dirname(args.outfname))

for dname in [args.cachedir, args.history_dir]:
    if not os.path.exists(dname):
        os.makedirs(dname + '/mtwx')
        os.makedirs(dname + '/noaa')

# ----------------------------------------------------------------------------------------
def get_mtwx_link(location, elevation):
    return 'http://www.mountain-forecast.com/peaks/' + location + '/forecasts/' + str(elevation)
def get_noaa_link(lat, lon):
    return 'http://forecast.weather.gov/MapClick.php?textField1=' + str(lat) + '&textField2=' + str(lon)
def get_wrf_links(location):
    return 'http://www.atmos.washington.edu/mm5rt/rt/load.cgi?latest+YYYYMMDDHH/images_d4/' + location + '.mg.gif+text+4/3%20km'

# ----------------------------------------------------------------------------------------
def get_mtwx(args, location_name, location_title, elevation, num_days=6, metric=False):
    filenamestr = location_name + '-' + str(elevation)
    url = get_mtwx_link(location_name, elevation)
    parser = etree.HTMLParser()

    cachefname = args.cachedir + '/mtwx/' + filenamestr + '.html'
    if args.use_cache:
        tree = etree.parse(cachefname, parser)
    else:
        tree = etree.parse(url, parser)
        tmpstr = etree.tostring(tree.getroot(), pretty_print=True, method='html')
        with open(cachefname, 'w') as tmpfile:
            tmpfile.write(tmpstr)

    mtp = mtwxparser.mtwxparser(num_days = num_days)
    forecast = mtp.forecast(args, tree, filenamestr, location_name, location_title, elevation, history_dir=args.history_dir + '/mtwx', htmldir=os.path.dirname(os.path.abspath(args.outfname)))

# ----------------------------------------------------------------------------------------
def get_noaa_forecast(args, location_name, elevation, lat, lon, start_date=datetime.date.today(), num_days=6, metric=False):
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

    cachefname = args.cachedir + '/noaa/' + location_name + '.xml'
    if args.use_cache:
        tree = ET.parse(cachefname)
    else:
        resp = urllib.urlopen(url)
        tree = ET.parse(resp)
        xmlstr = ET.tostring(tree.getroot())
        with open(cachefname, 'w') as tmpfile:
            tmpfile.write(xmlstr)
        if 'No data were found using the following input:' in xmlstr:
            print '    No data found for %s' % location_name
            return None

    forecast = ndfdparser.forecast(args, tree, location_name, elevation, htmldir=os.path.dirname(os.path.abspath(args.outfname)))
    return forecast

# ----------------------------------------------------------------------------------------
# read config csvs
mtwx_locations = OrderedDict()
with open(args.mtwx_location_fname) as mtwx_location_file:
    reader = csv.DictReader(filter(lambda row: row[0]!='#', mtwx_location_file))
    for line in reader:
        mtwx_locations[line['title']] = line

noaa_locations = OrderedDict()
with open(args.noaa_location_fname) as noaa_location_file:
    reader = csv.DictReader(filter(lambda row: row[0]!='#', noaa_location_file))
    for line in reader:
        noaa_locations[line['name']] = line

# ----------------------------------------------------------------------------------------
# write html file
layout = [
    ['Washington & Co.'],
    ['mtwx/Kulshan', 'noaa/Cathedral Peak'],
    ['mtwx/Mirkwood', 'mtwx/Liberty Bell'],
    ['mtwx/Luna Peak', 'mtwx/Dakobed'],
    ['noaa/Stevens Pass', 'noaa/Leavenworth'],
    ['mtwx/Snoqualmie Mtn', 'mtwx/Dragontail'],
    ['mtwx/Tahoma', 'mtwx/Paradise'],
    ['mtwx/Mt Olympus', 'noaa/Vantage'],
    ['noaa/Index', 'noaa/North Bend'],
    ['noaa/Strobach', 'noaa/Tieton'],
    ['mtwx/Mt Hood', 'noaa/Smith Rock'],

    ['Great White North'],
    ['mtwx/Devils Thumb', ''],
    ['mtwx/Mt Waddington', 'mtwx/Slesse'],
    ['mtwx/Serratus', 'mtwx/Stawamus Chief'],

    ['California'],
    ['mtwx/Shasta', 'noaa/Bishop'],
    ['mtwx/Yosemite', 'noaa/Joshua Tree'],

    ['Townships'],
    ['noaa/Seattle', '']
]

htmlheaders = ['<style> h1 { font-size: 150%; } </style>',
               'retrieved %s<br>' % datetime.datetime.now().strftime('%a %B %d %Y at %H:%M'),
               '<br><a href="http://psathyrella.github.io/wrfparser/4km_3-hour-precip.html">uw wrf interface</a><br>'
]
htmllist = ['\n'.join(htmlheaders)]
newrowlist = []
for loclist in layout:

    if len(loclist) == 1:  # section header
        if len(newrowlist) > 0:
            htmllist.append(HTML.table(newrowlist))
            newrowlist = []
        htmllist.append('<br><h1>' + loclist[0] + '</h1><br>')
        continue

    header, row = [], []
    for location in loclist:
        if location == '':
            continue
        ltype, name = location.split('/')
        if ltype == 'mtwx' and name in mtwx_locations:
            elevation_meters = int(mtwx_locations[name]['elevation'])
            elevation_nearest_foot = int(mtwxparser.meters_to_feet(elevation_meters))
            elevation_nearest_hundred_feet = str(int(round(elevation_nearest_foot, -2)))
            # NOTE confusing screw up of name/title distinction here
            fname = 'mtwx/' + mtwx_locations[name]['name'] + '-' + str(elevation_meters) + '.svg'  # elevation in meters
            loc_name_str = mtwx_locations[name]['title']
            elevation_str = elevation_nearest_hundred_feet
            url = get_mtwx_link(mtwx_locations[name]['name'], elevation_meters)
        elif ltype == 'noaa' and name in noaa_locations:
            loc_name_str = noaa_locations[name]['name']
            elevation_str = noaa_locations[name]['elevation']
            url = get_noaa_link(noaa_locations[name]['lat'], noaa_locations[name]['lon'])
            fname = 'noaa/' + name + '.svg'
        else:
            print 'couldn\'t find %s' % location
            continue
            # raise Exception('bad ltype %s' % ltype)
        headstr = '<a href="%s">%s</a> (%s ft)' % (url, loc_name_str, elevation_str)
        header.append(headstr)
        row.append('<a target="_blank" href="' + fname + '"><img  src="' + fname + '" alt="weather" width="500" height="175">')
    newrowlist.append(header)
    newrowlist.append(row)
print 'TODO clean up unit treatment'
print 'TODO get wind direction for noaa'
htmllist += HTML.table(newrowlist)
notes = ['<h1>Notes</h1>',
         '<ul>',
         '<li>Weather for the last n days is the forecast archived the day before, i.e. somewhat less than 24 hours in advance, of the indicated date.</li>',
         '<li>More history (in csvs, for the moment) can be found <a href="https://github.com/psathyrella/weatherhistory">here</a></li>',
         '<li>Some forecasts are from noaa\'s ndfd server, and some are from mountain-forecast. They report somewhat different information, hence two slightly different plotting styles.</li>',
         '<li>ndfd gives me snow and total precip, and in order to make it consistent with the mountain-forecast plots (which have snow and rain), I very hackily and approximately subtract snow in feet from the total precip in inches to get rain. This is why it sometimes looks like it\'s raining a little bit at the top of Tahoma in the middle of winter.</li>',
         '<li>It would be unbelievably awesome to use UW\'s WRF as a source for everything. It has much smaller grids, which would help a lot. But they only make available the jenky useless-ish gif things <a href="http://www.atmos.washington.edu/mm5rt/gfsinit.html">here</a>, which are impossible to pull actual numbers from.</li>',
         '<li>If all the wind arrows are pointing north, that\'s \'cause I don\'t have the direction information. I need to add it</li>',
         '<li>Have a suggestion? Submit an <a href="https://github.com/psathyrella/weatherscraper/issues/new">issue</a> (hmm, darn, they make you get a [free] account for that... um, working on this)'
         '</ul>',
         ]
newhtmlcode = ''.join(htmllist) + '\n'.join(notes)
newhtmlfile = open(args.outfname, 'w')
newhtmlfile.write(newhtmlcode)
newhtmlfile.close()
# sys.exit()        

# ----------------------------------------------------------------------------------------
# get mtwx forecasts
for name, line in mtwx_locations.items():
    print '\n%s:' % line['name']
    get_mtwx(args, line['name'], line['title'], line['elevation'])
# sys.exit()
# ----------------------------------------------------------------------------------------
# and then noaa forecasts
rows = []
fails = []
print 'TODO remove all the cruft from the old style plots'
for name, line in noaa_locations.items():
    print '\n%s:' % line['name']
    args.location = ()  # TODO not sure why I do this
    n_tries = 0
    # while n_tries < 3:
    days, forecast = get_noaa_forecast(args, line['name'], float(line['elevation']), line['lat'], line['lon'])
    try:
        # days, forecast = get_noaa_forecast(args, line['name'], float(line['elevation']), line['lat'], line['lon'])
        extrastr = line['name'] + '<br>'
        extrastr += '<font size="2">' + line['elevation'] + ' ft <br></font>'
        if line['mtwx-location'] != '':
            extrastr += '<font size="2"><a href="' + get_mtwx_link(line['mtwx-location'], line['mtwx-elevation']) + '">mtfcast</a></font>'
        forecast[0] = forecast[0].replace('LOCATION', extrastr)
        rows.append(forecast)
        # break
    except AttributeError:
        fails.append(line['name'])
    n_tries += 1

if not args.old_style:
    sys.exit()

# ----------------------------------------------------------------------------------------
# write old-style html output
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
    sundries.append(['<a href="' + get_mtwx_link('Mount-Waddington', 4016) + '">Waddington</a>', ])
    sundries.append(['<a href="' + get_mtwx_link('Slesse-Peak', 2393) + '">Slesse</a>', ])
    sundries.append(['<a href="' + get_mtwx_link('Serratus-Mountain', 2321) + '">Serratus</a>', ])
    sundries.append(['<a href="http://weather.gc.ca/city/pages/bc-50_metric_e.html">Squamish</a>', ])
    outfile.write(HTML.table(sundries, header_row=['<b>sundries</b><br>', ]))
    if not args.no_history:
        outfile.write('<br>Note: "history" is the point forecast archived the day before, i.e. somewhat less than 24 hours in advance, of the indicated date.<br>')
    outfile.write('<br><br><a href=\"https://github.com/psathyrella/weatherscraper\">github</a><br><br>')
    if len(fails) > 0:
        outfile.write('wget failed (ndfd server getting ddos\'d?) for:<br>')
        outfile.write('<br>'.join(fails))
