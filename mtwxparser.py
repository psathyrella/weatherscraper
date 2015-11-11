from datetime import datetime, timedelta
from lxml import etree
import os
import sys
import csv
from collections import OrderedDict

import plotting

# now = datetime.now()
# rounded_now = datetime(now.year, now.month, now.day)
variables = ['date', 'time-of-day', 'wind-speed', 'snow', 'rain', 'high', 'low']
times_of_day = ['AM', 'PM', 'night']
weekdays = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
# tv['days'].append(weekdays[day.weekday()])
imperial_units = True

# ----------------------------------------------------------------------------------------
def kph_to_mph(speed):
    return 0.62137119 * speed
def celsius_to_fahrenheit(temp):
    return 1.8 * temp + 32.
def cm_to_in(distance):
    return 0.39370079 * distance
def cm_to_feet(distance):
    return 0.39370079 * distance / 12
def mm_to_in(distance):
    return 0.039370079 * distance
def meters_to_feet(distance):
    return 39.370079 * distance / 12

# ----------------------------------------------------------------------------------------
def init_data(num_days):
    data = []

    def add_empty_forecast(date, tod):
        data.append({})
        for var in variables:
            if var == 'date':
                data[-1][var] = date
            elif var == 'time-of-day':
                data[-1][var] = tod
            else:
                data[-1][var] = None

    now = datetime.now()
    for iday in range(num_days):
        thisday = now + timedelta(iday)  # NOTE time is arbitrary here (well, it's the time we retrieved it at, but you shouldn't use it for anything)
        for tod in times_of_day:
            add_empty_forecast(thisday, tod)
    return data

# ----------------------------------------------------------------------------------------
def parse_days(tr, data):
    """ really just checks to make sure we get the days we expect from the html """
    htmldays, htmldates = [], []
    for child in tr:
        if child.tag == 'th':  # header info
            if child.find('.//nobr').text != 'Metric':  # this isn't saying the numbers are metric (although they probably are), it's just how they arrange the radio buttons
                raise Exception('either an unexpected tag, or the wrong units')
        elif child.tag == 'td':  # data
            # print child.keys()
            weekday = child.find('b').text
            day_of_month = int(child.find('b').tail)
            htmldays.append(weekday)
            htmldates.append(day_of_month)
        else:
            raise Exception('unexpected tag %s' % child.tag)

    if len(data) / 3 != len(htmldays):
        raise Exception('different number of days in data %d and html %d' % (len(data), len(htmldays)))
    for iday in range(len(htmldays)):
        if weekdays[data[3*iday]['date'].weekday()] not in htmldays[iday]:
            raise Exception('days don\'t match up %s %s' % (data[3*iday]['date'].weekday(), htmldays[iday]))
        if htmldates[iday] != data[3*iday]['date'].day:
            raise Exception('dates don\'t match up %s %s' % (data[3*iday]['date'], htmldates[iday]))

# ----------------------------------------------------------------------------------------
def parse_wind(tr, data):
    speedlist, directionlist = [], []
    for child in tr:
        if child.tag == 'th':  # header info
            units = child.find('.//span').text
            if units != 'km/h':
                raise Exception('unexpected wind units %s' % units)
        elif child.tag == 'td':  # data
            img = child.find('.//img')
            speed, direction = img.get('alt').split()
            speed = int(speed)

            span = child.find('.//span')
            if int(span.text) != speed:  # they put the info in there twice, we may as well make sure it's the same
                raise Exception('wind speeds don\'t match up %d %d' % (speed, int(span.text)))

            if imperial_units:
                speed = kph_to_mph(speed)

            speedlist.append(speed)
            directionlist.append(direction)
        else:
            raise Exception('unexpected tag %s' % child.tag)

    if len(data) != len(speedlist):
        raise Exception('different number of days in data %d and html %d' % (len(data), len(speedlist)))
    for ifc in range(len(speedlist)):
        data[ifc]['wind-speed'] = speedlist[ifc]

# ----------------------------------------------------------------------------------------
def parse_simple(name, tr, data, expected_units):
    fcastlist = []
    for child in tr:
        if child.tag == 'th':  # header info
            span = child.find('.//span')
            # if span.get('class') != name + 'u':
            #     raise Exception('unexpeced class name %s (expected %s)' % (span.get('class'), name + 'u'))
            units = child.find('.//span').text
            if units != expected_units:
                raise Exception('bad units: expected %s but got  %s' % (expected_units, units))
        elif child.tag == 'td':  # data
            span = child.find('.//span')
            # if span.get('class') != name:
            #     raise Exception('unexpected name %s (instead of %s)' % (span.get('class'), name))
            value = 0 if span.text == '-' else int(span.text)

            if imperial_units:
                if expected_units == 'cm':
                    value = cm_to_feet(value)
                elif expected_units == 'mm':
                    value = mm_to_in(value)
                elif expected_units == 'C':
                    value = celsius_to_fahrenheit(value)

            fcastlist.append(value)

    if len(data) != len(fcastlist):
        raise Exception('different number of days in data %d and html %d' % (len(data), len(fcastlist)))
    for ifc in range(len(fcastlist)):
        data[ifc][name] = fcastlist[ifc]

# ----------------------------------------------------------------------------------------
def ascii(data):
    print '%-5s          %4s   %5s%5s' % ('', 'hi lo', 'snow    rain ', 'wind')
    for fcast in data:
        time = fcast['time-of-day']
        if time == 'AM':
            time = ('%-5s' % weekdays[fcast['date'].weekday()]) + '  ' + time
        else:
            time = '       ' + time
        print '%-12s %4.0f %-3.0f  %5.2f %5s   %5.1f' % (time, fcast['high'], fcast['low'], fcast['snow'], fcast['rain'], fcast['wind-speed'])

# ----------------------------------------------------------------------------------------
def combine_times_of_day(fcast):
    """ 
    sum/average/minmax as appropriate over AM, PM, night
    NOTE <fcast> must be a list of length 3, for AM PM night
    """
    if len(fcast) != len(times_of_day):
        print fcast
        raise Exception('bad fcast')
    daily_fcast = {'date' : fcast[0]['date'],
                   'wind-speed' : -9999.,
                   'snow' : 0.,
                   'rain' : 0.,
                   'high' : -99999.,
                   'low' : 99999.}

    today = datetime.now()
    for itod in range(len(times_of_day)):  # sum/average/minmax over the three times of day
        # if fcast[itod]['date'].month != today.month or fcast[itod]['date'].day != today.day or fcast[itod]['time-of-day'] != times_of_day[itod]:
        #     print fcast[itod]['date']
        #     print today
        #     raise Exception('dates don\'t match')

        if fcast[itod]['wind-speed'] > daily_fcast['wind-speed']:  # use the max wind speed
            daily_fcast['wind-speed'] = fcast[itod]['wind-speed']
        daily_fcast['snow'] += fcast[itod]['snow']
        daily_fcast['rain'] += fcast[itod]['rain']
        if fcast[itod]['high'] > daily_fcast['high']:
            daily_fcast['high'] = fcast[itod]['high']
        if fcast[itod]['low'] < daily_fcast['low']:
            daily_fcast['low'] = fcast[itod]['low']

        return daily_fcast

# ----------------------------------------------------------------------------------------
def combine_all_times_of_day(forecasts):
    tod_list = [[forecasts[3*i], forecasts[3*i + 1], forecasts[3*i + 2]] for i in range(len(forecasts)/3)]
    # for td in tod_list:
    #     print td[0]['date'].day, td[0]['time-of-day'], td[1]['date'].day, td[1]['time-of-day'], td[2]['date'].day, td[2]['time-of-day']
    daily_forecasts = []
    for tod in tod_list:
        daily_forecasts.append(combine_times_of_day(tod))
    return daily_forecasts

# ----------------------------------------------------------------------------------------
def read_and_write_history(history_fname, todaysdata):
    """ write today's forecast to a csv for later retrieval """
    history = OrderedDict()
    history_header = ('month', 'day', 'year', 'high', 'low', 'rain', 'snow', 'wind')
    if os.path.exists(history_fname):  # read in any existing history
        with open(history_fname, 'r') as historyfile:
            reader = csv.DictReader(historyfile)
            for line in reader:
                key = datetime(int(line['year']), int(line['month']), int(line['day']))
                history[key] = line
    elif not os.path.exists(os.path.dirname(history_fname)):
        os.makedirs(os.path.dirname(history_fname))

    today = datetime.now()
    rounded_today = datetime(today.year, today.month, today.day)  # no hours and minutes and whatnot

    daily_fcast = combine_times_of_day(todaysdata)

    if rounded_today in history:
        print 'replacing'
    history[rounded_today] = {'month' : today.month,
                              'day' : today.day,
                              'year' : today.year,
                              'high' : daily_fcast['high'],
                              'low' : daily_fcast['low'],
                              'rain' : daily_fcast['rain'],
                              'snow' : daily_fcast['snow'],
                              'wind' : daily_fcast['wind-speed']}

    with open(history_fname, 'w') as historyfile:
        writer = csv.DictWriter(historyfile, history_header)
        writer.writeheader()
        for line in history.values():
            writer.writerow(line)

    # make something to return (for plotting)
    history_list = []
    for index, values in history.items():
        date = datetime(int(values['year']), int(values['month']), int(values['day']))
        now = datetime.now()
        # if timedelta(abs(date - datetime.now())) < timedelta(hours=12):  # don't add today
        if date.year == now.year and date.month == now.month and date.day == now.day:
            continue
        valdict = {}
        for k, v in values.items():
            if k != 'month' and k != 'day' and k != 'year':
                valdict[k] = v
        valdict['date'] = date
        history_list.append(valdict)
    return history_list

# ----------------------------------------------------------------------------------------
def forecast(args, tree, location_name, mtfcast_name, elevation, num_days, history_dir, htmldir):
    # print etree.tostring(tree.getroot(), pretty_print=True, method='html')
    forecasts = init_data(num_days)
    # tmpstr = etree.tostring(tree.getroot(), pretty_print=True, method='html')
    # with open('tmp.html', 'w') as tmpfile:
    #     tmpfile.write(tmpstr)
    for tr in tree.findall('.//tr'):
        keys = tr.keys()
        thlist = tr.findall('th')
        tdlist = tr.findall('td')
        if 'class' in keys and tr.get('class') == 'lar hea ':
            parse_days(tr, forecasts)
        elif 'class' in keys and tr.get('class') == 'lar hea1':  # am/pm header
            pass
        elif len(thlist) > 0 and thlist[0].text.strip() == 'Wind':
            parse_wind(tr, forecasts)
        elif len(thlist) > 0 and thlist[0].text.strip() == 'Snow (':
            parse_simple('snow', tr, forecasts, expected_units='cm')
        elif len(thlist) > 0 and thlist[0].text.strip() == 'Rain (':
            parse_simple('rain', tr, forecasts, expected_units='mm')
        elif len(thlist) > 0 and 'High' in thlist[0].text:
            parse_simple('high', tr, forecasts, expected_units='C')
        elif len(thlist) > 0 and 'Low' in thlist[0].text:
            parse_simple('low', tr, forecasts, expected_units='C')
        else:
            pass

    ascii(forecasts)

    daily_forecasts = combine_all_times_of_day(forecasts)
    history = read_and_write_history(history_dir + '/' + mtfcast_name + '-' + str(elevation) + '.csv', forecasts[0 : 3])
    plotdir = htmldir + '/mtfcast/forecast/'
    if not os.path.exists(plotdir):
        os.makedirs(plotdir)
    plotting.make_mtfcast_plot(args, mtfcast_name, location_name, int(meters_to_feet(int(elevation))), plotdir, forecasts, history, daily_forecasts)
