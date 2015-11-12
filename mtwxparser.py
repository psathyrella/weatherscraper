import datetime
from lxml import etree
import os
import sys
import math
import numpy
import csv
from collections import OrderedDict

import plotting
import utils

imperial_units = True
forecasts_to_skip = [0, 1, 17]

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
class mtwxparser(object):
    def __init__(self):
        self.skip_todays_forecast = False  # they've stopped showing today's AM forecast, and are showning the AM for the sixth day out

    # ----------------------------------------------------------------------------------------
    def init_data(self, num_days):
        data = []
    
        def add_empty_forecast(date, tod):
            data.append({})
            for var in utils.variables:
                if var == 'date':
                    data[-1][var] = date
                elif var == 'time-of-day':
                    data[-1][var] = tod
                else:
                    data[-1][var] = None
    
        today = datetime.date.today()
        for iday in range(num_days):
            thisday = today + datetime.timedelta(iday)
            for tod in utils.times_of_day:
                add_empty_forecast(thisday, tod)
        return data
    
    # ----------------------------------------------------------------------------------------
    def parse_days(self, tr, data):
        """ really just checks to make sure we get the days we expect from the html """
        htmldays, htmldates = [], []
        for child in tr:
            if child.tag == 'th':  # header info
                if child.find('.//nobr').text != 'Metric':  # this isn't saying the numbers are metric (although they probably are), it's just how they arrange the radio buttons
                    raise Exception('either an unexpected tag, or the wrong units')
            elif child.tag == 'td':  # data
                # print child.keys()
                if child.find('b') is None:
                    print 'missing date... it\'s probably late enough in the day that they\'re not printing the mornign forecast any more'
                    self.skip_todays_forecast = True
                    for i in range(len(utils.times_of_day)):
                        data.pop(0)
                    return
                weekday = child.find('b').text
                day_of_month = int(child.find('b').tail)
                htmldays.append(weekday)
                htmldates.append(day_of_month)
            else:
                raise Exception('unexpected tag %s' % child.tag)
    
        if len(data) / 3 != len(htmldays):
            raise Exception('different number of days in data %d and html %d' % (len(data), len(htmldays)))
        for iday in range(len(htmldays)):
            if utils.weekdays[data[3*iday]['date'].weekday()] not in htmldays[iday]:
                raise Exception('days don\'t match up %s %s' % (data[3*iday]['date'].weekday(), htmldays[iday]))
            if htmldates[iday] != data[3*iday]['date'].day:
                raise Exception('dates don\'t match up %s %s' % (data[3*iday]['date'], htmldates[iday]))
    
    # ----------------------------------------------------------------------------------------
    def parse_wind(self, tr, data):
        speedlist, directionlist = [], []
        itd = 0
        for child in tr:
            if child.tag == 'th':  # header info
                units = child.find('.//span').text
                if units != 'km/h':
                    raise Exception('unexpected wind units %s' % units)
            elif child.tag == 'td':  # data
                if self.skip_todays_forecast:
                    if itd in forecasts_to_skip:
                        itd += 1
                        continue
                img = child.find('.//img')
                speed, direction = img.get('alt').split()
                speed = int(speed)
                direction = utils.convert_wind_direction_to_angle(direction)
    
                span = child.find('.//span')
                if int(span.text) != speed:  # they put the info in there twice, we may as well make sure it's the same (NOTE one of these stays in kph in the source html if you click the 'imperial' radio button)
                    raise Exception('wind speeds don\'t match up %d %d' % (speed, int(span.text)))
    
                if imperial_units:
                    speed = kph_to_mph(speed)
    
                speedlist.append(speed)
                directionlist.append(direction)
                itd += 1
            else:
                raise Exception('unexpected tag %s' % child.tag)
    
        if len(data) != len(speedlist):
            raise Exception('different number of days in data %d and html %d' % (len(data), len(speedlist)))
        for ifc in range(len(speedlist)):
            data[ifc]['wind-speed'] = speedlist[ifc]
            data[ifc]['wind-direction'] = directionlist[ifc]
    
    # ----------------------------------------------------------------------------------------
    def parse_simple(self, name, tr, data, expected_units):
        fcastlist = []
        itd = 0
        for child in tr:
            if child.tag == 'th':  # header info
                span = child.find('.//span')
                # if span.get('class') != name + 'u':
                #     raise Exception('unexpeced class name %s (expected %s)' % (span.get('class'), name + 'u'))
                units = child.find('.//span').text
                if units != expected_units:
                    raise Exception('bad units: expected %s but got  %s' % (expected_units, units))
            elif child.tag == 'td':  # data
                if self.skip_todays_forecast:
                    if itd in forecasts_to_skip:
                        itd += 1
                        continue
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
                itd += 1
    
        if len(data) != len(fcastlist):
            raise Exception('different number of days in data %d and html %d' % (len(data), len(fcastlist)))
        for ifc in range(len(fcastlist)):
            data[ifc][name] = fcastlist[ifc]
    
    # ----------------------------------------------------------------------------------------
    def ascii(self, data):
        print '%-5s          %5s     %5s   %5s    %5s' % ('', 'hi lo', 'snow (ft)', 'rain (in)', 'wind')
        for fcast in data:
            time = fcast['time-of-day']
            if time == 'AM':
                time = ('%-5s' % utils.weekdays[fcast['date'].weekday()]) + '  ' + time
            else:
                time = '       ' + time
            print '%-12s %4.0f %-3.0f     %5.2f     %5s       %5.1f  %s' % (time, fcast['high'], fcast['low'], fcast['snow'], fcast['rain'], fcast['wind-speed'], fcast['wind-direction'])
    
    # ----------------------------------------------------------------------------------------
    def combine_times_of_day(self, fcast):
        """ 
        sum/average/minmax as appropriate over AM, PM, night
        NOTE <fcast> must be a list of length 3, for AM PM night
        """
        if len(fcast) != len(utils.times_of_day):
            print fcast
            raise Exception('bad fcast')
        daily_fcast = {'date' : fcast[0]['date'],
                       'wind-speed' : -9999.,
                       'wind-direction' : 0.,
                       'snow' : 0.,
                       'rain' : 0.,
                       'high' : -99999.,
                       'low' : 99999.}
    
        for itod in range(len(utils.times_of_day)):  # sum/average/minmax over the three times of day
            if fcast[itod]['wind-speed'] > daily_fcast['wind-speed']:  # use the max wind speed
                daily_fcast['wind-speed'] = fcast[itod]['wind-speed']
                daily_fcast['wind-direction'] = fcast[itod]['wind-direction']  # just keep track of the direction of the max wind
            daily_fcast['snow'] += fcast[itod]['snow']
            daily_fcast['rain'] += fcast[itod]['rain']
            if fcast[itod]['high'] > daily_fcast['high']:
                daily_fcast['high'] = fcast[itod]['high']
            if fcast[itod]['low'] < daily_fcast['low']:
                daily_fcast['low'] = fcast[itod]['low']
    
        return daily_fcast
    
    # ----------------------------------------------------------------------------------------
    def combine_all_times_of_day(self, forecasts):
        tod_list = [[forecasts[3*i], forecasts[3*i + 1], forecasts[3*i + 2]] for i in range(len(forecasts)/3)]
        # for td in tod_list:
        #     print td[0]['date'].day, td[0]['time-of-day'], td[1]['date'].day, td[1]['time-of-day'], td[2]['date'].day, td[2]['time-of-day']
        daily_forecasts = []
        for tod in tod_list:
            daily_forecasts.append(self.combine_times_of_day(tod))
        return daily_forecasts
    
    # ----------------------------------------------------------------------------------------
    def read_and_write_history(self, history_fname, current_forecasts):
        """ write today's forecast to a csv for later retrieval """
        history = []
        if os.path.exists(history_fname):  # read in any existing history
            with open(history_fname, 'r') as historyfile:
                reader = csv.DictReader(historyfile)
                for line in reader:
                    date = datetime.date(int(line['year']), int(line['month']), int(line['day']))
                    for k, v in line.items():
                        if k == 'month' or k == 'day' or k == 'year':
                            del line[k]
                        elif k == 'time-of-day':
                            pass
                        else:
                            line[k] = float(v)
                    line['date'] = date
                    history.append(line)
        elif not os.path.exists(os.path.dirname(history_fname)):
            os.makedirs(os.path.dirname(history_fname))
    
        today = datetime.date.today()
        if current_forecasts[0]['date'] == today and history[-3]['date'] == today:  # replace forecast in history with that from <current_forecasts>
            print 'not replacing history'
            # for itod in range(len(utils.times_of_day)):
            #     tod = utils.times_of_day[itod]
            #     if today_key + '-' + tod in history and current_forecasts[0]['date'] == :
            #         print 'replacing %s' % tod
            #         fcast = todaysdata[utils.times_of_day.index(tod)]
            #         history[rounded_today] = {'year' : today.year,
            #                                   'month' : today.month,
            #                                   'day' : today.day,
            #                                   'time-of-day' : tod,
            #                                   'high' : fcast['high'],
            #                                   'low' : fcast['low'],
            #                                   'rain' : fcast['rain'],
            #                                   'snow' : fcast['snow'],
            #                                   'wind-speed' : fcast['wind-speed'],
            #                                   'wind-direction' : fcast['wind-direction']}
        else:
            print 'current forecast is missing today, use history instead'
            current_forecasts = [history[-3], history[-2], history[-1]] + current_forecasts
            # for itod in range(len(utils.times_of_day), 0, -1):
            #     print history[len(history) - itod]['date']
            #     assert history[len(history) - itod]['date'] == today
            #     current_forecasts.insert(0, history[len(history) - itod])
    
        history_header = ('month', 'day', 'year', 'time-of-day', 'high', 'low', 'rain', 'snow', 'wind-speed', 'wind-direction')
        with open(history_fname, 'w') as historyfile:
            writer = csv.DictWriter(historyfile, history_header)
            writer.writeheader()
            for fcast in history:
                dcast = dict(fcast)
                dcast['month'] = dcast['date'].month
                dcast['day'] = dcast['date'].day
                dcast['year'] = dcast['date'].year
                del dcast['date']
                writer.writerow(dcast)
    
        # # make something to return (for plotting)
        # history_list = []
        # for index, values in history.items():
        #     # date = datetime.datetime(int(values['year']), int(values['month']), int(values['day']))
        #     # now = datetime.datetime.now()
        #     # if date.year == now.year and date.month == now.month and date.day == now.day:
        #     #     continue
        #     valdict = {}
        #     for k, v in values.items():
        #         if k != 'month' and k != 'day' and k != 'year':
        #             if k == 'time-of-day':
        #                 valdict[k] = v
        #             else:
        #                 valdict[k] = float(v)  # we can leave these as strings earlier 'cause we're just writing them straight back into the file
        #     valdict['date'] = date
        #     history_list.append(valdict)
        # return history_list
        return current_forecasts, history
    
    # ----------------------------------------------------------------------------------------
    def forecast(self, args, tree, location_name, mtfcast_name, elevation, num_days, history_dir, htmldir):
        # print etree.tostring(tree.getroot(), pretty_print=True, method='html')
        forecasts = self.init_data(num_days)
        # tmpstr = etree.tostring(tree.getroot(), pretty_print=True, method='html')
        # with open('tmp.html', 'w') as tmpfile:
        #     tmpfile.write(tmpstr)
        for tr in tree.findall('.//tr'):
            keys = tr.keys()
            thlist = tr.findall('th')
            tdlist = tr.findall('td')
            if 'class' in keys and tr.get('class') == 'lar hea ':
                self.parse_days(tr, forecasts)
            elif 'class' in keys and tr.get('class') == 'lar hea1':  # am/pm header
                pass
            elif len(thlist) > 0 and thlist[0].text.strip() == 'Wind':
                self.parse_wind(tr, forecasts)
            elif len(thlist) > 0 and thlist[0].text.strip() == 'Snow (':
                self.parse_simple('snow', tr, forecasts, expected_units='cm')
            elif len(thlist) > 0 and thlist[0].text.strip() == 'Rain (':
                self.parse_simple('rain', tr, forecasts, expected_units='mm')
            elif len(thlist) > 0 and 'High' in thlist[0].text:
                self.parse_simple('high', tr, forecasts, expected_units='C')
            elif len(thlist) > 0 and 'Low' in thlist[0].text:
                self.parse_simple('low', tr, forecasts, expected_units='C')
            else:
                pass
    
        forecasts, history = self.read_and_write_history(history_dir + '/' + mtfcast_name + '-' + str(elevation) + '.csv', forecasts)  # potentially modifies <forecasts>
        self.ascii(forecasts)
        plotdir = htmldir + '/mtfcast/forecast/'
        if not os.path.exists(plotdir):
            os.makedirs(plotdir)
        daily_forecasts = self.combine_all_times_of_day(forecasts)
        daily_history = self.combine_all_times_of_day(history)
        plotting.make_mtfcast_plot(args, mtfcast_name, location_name, int(meters_to_feet(int(elevation))), plotdir, forecasts, daily_history, daily_forecasts)
