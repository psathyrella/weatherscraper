from datetime import datetime, timedelta
from lxml import etree
import sys

# now = datetime.now()
# rounded_now = datetime(now.year, now.month, now.day)
variables = ['date', 'time-of-day', 'wind-speed', 'snow', 'rain', 'high', 'low']
times_of_day = ['AM', 'PM', 'night']
weekdays = ('Mon', 'Tues', 'Wed', 'Thurs', 'Fri', 'Sat', 'Sun')
# tv['days'].append(weekdays[day.weekday()])
imperial_units = True

# ----------------------------------------------------------------------------------------
def kph_to_mph(speed):
    return 0.62137119 * speed
def celsius_to_fahrenheit(temp):
    return 1.8 * temp + 32.
def cm_to_in(distance):
    return 0.39370079 * distance
def mm_to_in(distance):
    return 0.039370079 * distance

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
                    value = cm_to_in(value)
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
def forecast(args, tree, num_days):
    # print etree.tostring(tree.getroot(), pretty_print=True, method='html')
    data = init_data(num_days)
    # tmpstr = etree.tostring(tree.getroot(), pretty_print=True, method='html')
    # with open('tmp.html', 'w') as tmpfile:
    #     tmpfile.write(tmpstr)
    for tr in tree.findall('.//tr'):
        keys = tr.keys()
        thlist = tr.findall('th')
        tdlist = tr.findall('td')
        if 'class' in keys and tr.get('class') == 'lar hea ':
            parse_days(tr, data)
        elif 'class' in keys and tr.get('class') == 'lar hea1':  # am/pm header
            pass
        elif len(thlist) > 0 and thlist[0].text.strip() == 'Wind':
            parse_wind(tr, data)
        elif len(thlist) > 0 and thlist[0].text.strip() == 'Snow (':
            parse_simple('snow', tr, data, expected_units='cm')
        elif len(thlist) > 0 and thlist[0].text.strip() == 'Rain (':
            parse_simple('rain', tr, data, expected_units='mm')
        elif len(thlist) > 0 and 'High' in thlist[0].text:
            parse_simple('high', tr, data, expected_units='C')
        elif len(thlist) > 0 and 'Low' in thlist[0].text:
            parse_simple('low', tr, data, expected_units='C')
        else:
            pass

    ascii(data)
    sys.exit()
