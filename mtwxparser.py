import datetime
from lxml import etree
import os
import sys
import copy
import math
import numpy
import csv
from collections import OrderedDict

import plotting
import utils

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
class mtwxparser(object):
    def __init__(self, num_days):
        self.max_history = 6
        self.num_days = num_days
        self.htmldates = []
        self.fcast_vals = ['high', 'low', 'rain', 'snow', 'wind-speed', 'wind-direction']
        self.history_header = ['month', 'day', 'year', 'time-of-day'] + self.fcast_vals

        self.today = datetime.date.today()
        self.expected_forecast_dates = [self.today + datetime.timedelta(days=i) for i in range(self.num_days)]  # NOTE *don't* add these to <self.forecasts> (yet -- see self.combine_times_of_day())
        self.forecasts = []
        self.todays_history, self.todays_forecast = [], []  # the first is read from history file, the second is taken from the forecasts if it's there, otherwise it's copied from the history info
        for tod in utils.times_of_day:
            self.add_empty_forecast(self.todays_history, self.today, tod)
            self.add_empty_forecast(self.todays_forecast, self.today, tod)
        self.expected_history_dates = [self.today - datetime.timedelta(days=i) for i in range(self.max_history, 0, -1)]
        self.history = []
        for ed in self.expected_history_dates:
            for tod in utils.times_of_day:
                self.add_empty_forecast(self.history, ed, tod) # = [{'date' : ed, 'time-of-day' : tod} for ed in self.expected_history_dates for tod in utils.times_of_day]
        self.old_history = []  # history we want to rewrite to the file, but not plot

    # ----------------------------------------------------------------------------------------
    def add_empty_forecast(self, data, date, tod):
        data.append({})
        for var in utils.variables:
            if var == 'date':
                data[-1][var] = date
            elif var == 'time-of-day':
                data[-1][var] = tod
            else:
                data[-1][var] = None

    # ----------------------------------------------------------------------------------------
    def parse_days(self, tr):
        """ really just checks to make sure we get the days we expect from the html """
        assert len(self.htmldates) == 0
        htmldays, htmldaynumbers = [], []
        itoday = None
        for child in tr:
            if child.tag == 'th':  # header info
                if child.find('.//nobr').text != 'Metric':  # this isn't saying the numbers are metric (although they probably are), it's just how they arrange the radio buttons
                    raise Exception('either an unexpected tag, or the wrong units')
            elif child.tag == 'td':  # data
                # print child.keys()
                if child.find('b') is None:  # if they don't give you all thre time periods for a day, there's no <b> tag, no date, and the day of week is abbreviated
                    weekday = child.text.strip()
                    day_of_month = None
                else:
                    weekday = child.find('b').text[:3]  # not abbreviated
                    day_of_month = int(child.find('b').tail)
                htmldays.append(weekday)
                htmldaynumbers.append(day_of_month)
                if weekday == utils.weekdays[self.today.weekday()]:
                    assert itoday is None
                    itoday = len(htmldays) - 1
            else:
                raise Exception('unexpected tag %s' % child.tag)

        if itoday is None:
            raise Exception('couldn\'t find today among %s (%s)' % (htmldays, htmldaynumbers))
        for iday in range(len(htmldays)):
            date = self.today - datetime.timedelta(days = itoday - iday)
            if htmldaynumbers[iday] is None:
                if iday != 0 and iday != len(htmldays) - 1:  # should either be at the start or the end
                    raise Exception('unexpected missing day %d' % iday)
                htmldaynumbers[iday] = date.day
            self.htmldates.append(date)

    # ----------------------------------------------------------------------------------------
    def parse_tods(self, tr):
        tods = []
        for child in tr:
            if child.tag == 'th':  # header info
                pass  # NOTE this is where the javascript to switch units is
            elif child.tag == 'td':
                if child.find('span') is not None:
                    tods.append(child.find('span').text)
                else:
                    raise Exception('unexpected tag in times of day %s' % child.tag)
            else:
                raise Exception('unexpected tag %s' % child.tag)

        iday = -1
        for tod in tods:
            if iday == -1 or tod == 'AM':
                iday += 1
            date = self.htmldates[iday]
            self.add_empty_forecast(self.forecasts, date, tod)

    # ----------------------------------------------------------------------------------------
    def parse_wind(self, tr):
        speedlist, directionlist = [], []
        itd = 0
        for child in tr:
            if child.tag == 'th':  # header info
                units = child.find('.//span').text
                if units != 'km/h':
                    raise Exception('unexpected wind units %s' % units)
            elif child.tag == 'td':  # data
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
    
        if len(self.forecasts) != len(speedlist):
            raise Exception('different number of days in data %d and html %d' % (len(self.forecasts), len(speedlist)))
        for ifc in range(len(speedlist)):
            self.forecasts[ifc]['wind-speed'] = speedlist[ifc]
            self.forecasts[ifc]['wind-direction'] = directionlist[ifc]
    
    # ----------------------------------------------------------------------------------------
    def parse_simple(self, name, tr, expected_units):
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
    
        if len(self.forecasts) != len(fcastlist):
            raise Exception('different number of days in data %d and html %d' % (len(self.forecasts), len(fcastlist)))
        for ifc in range(len(fcastlist)):
            self.forecasts[ifc][name] = fcastlist[ifc]
    
    # ----------------------------------------------------------------------------------------
    def ascii(self, data):
        print '%-5s          %5s     %5s   %5s    %5s' % ('', 'hi lo', 'snow (ft)', 'rain (in)', 'wind')
        for ifc in range(len(data)):
            fcast = data[ifc]
            time = fcast['time-of-day']
            if time == 'AM' or ifc == 0:
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
            for key in self.fcast_vals:
                if key in daily_fcast and daily_fcast[key] is None:  # already added it as None
                    continue
                if fcast[itod][key] is None:
                    daily_fcast[key] = None
                    continue
                if key == 'wind-speed' and fcast[itod]['wind-speed'] > daily_fcast['wind-speed']:  # use the max wind speed
                    daily_fcast['wind-speed'] = fcast[itod]['wind-speed']
                    daily_fcast['wind-direction'] = fcast[itod]['wind-direction']  # just keep track of the direction of the max wind
                elif key == 'wind-direction':  # fill this in while doing 'wind-speed'
                    continue
                elif key == 'snow' or key == 'rain':
                    daily_fcast[key] += fcast[itod][key]
                elif key == 'high' and fcast[itod][key] > daily_fcast[key]:
                    daily_fcast[key] = fcast[itod][key]
                elif key == 'low' and fcast[itod][key] < daily_fcast[key]:
                    daily_fcast[key] = fcast[itod][key]
        return daily_fcast
    
    # ----------------------------------------------------------------------------------------
    def combine_all_times_of_day(self, forecasts):
        # print '----'
        # for fc in forecasts:
        #     print fc['date'], '    ', fc
        tod_list = [[forecasts[3*i], forecasts[3*i + 1], forecasts[3*i + 2]] for i in range(len(forecasts)/3)]
        # for td in tod_list:
        #     print td[0]['date'].day, td[0]['time-of-day'], td[1]['date'].day, td[1]['time-of-day'], td[2]['date'].day, td[2]['time-of-day']
        daily_forecasts = []
        for tod in tod_list:
            daily_forecasts.append(self.combine_times_of_day(tod))
        return daily_forecasts
    
    # ----------------------------------------------------------------------------------------
    def read_history(self, history_fname):
        if not os.path.exists(history_fname):
            return

        def read_history_line(csvline, historyline):
            """  add values from <csvline> to <historyline> """
            for k, v in csvline.items():
                if k == 'month' or k == 'day' or k == 'year':  # only break apart the date for writing -- in the code we use a date object
                    pass
                elif k == 'time-of-day':
                    pass
                else:
                    assert historyline['date'] == date
                    historyline[k] = float(v)

        found_days = OrderedDict()  # set of days for which we have history
        with open(history_fname, 'r') as historyfile:
            reader = csv.DictReader(historyfile)
            for line in reader:
                date = datetime.date(int(line['year']), int(line['month']), int(line['day']))
                itod = utils.times_of_day.index(line['time-of-day'])
                if date == self.today:
                    read_history_line(line, self.todays_history[itod])
                    continue
                elif date in self.expected_history_dates:
                    idate = 3*self.expected_history_dates.index(date) + itod
                else:  # add to old_history
                    idate = None
                if date not in found_days:
                    found_days[date] = set()
                if line['time-of-day'] in found_days[date]:
                    raise Exception('got duplicate history %s %s' % (date, line['time-of-day']))
                else:
                    found_days[date].add(line['time-of-day'])
                if idate is None:
                    self.old_history.append({'date' : date, 'time-of-day' : line['time-of-day']})
                    read_history_line(line, self.old_history[-1])
                else:
                    read_history_line(line, self.history[idate])

    # ----------------------------------------------------------------------------------------
    def combine_history_and_forecasts(self, debug=False):
        # print 'OLD'
        # for fc in self.old_history:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']
        # print 'HISTORY'
        # for fc in self.history:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']
        # print 'TODAYS HISTORY'
        # for fc in self.todays_history:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']
        # print 'forecasts'
        # for fc in self.forecasts:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']

        # remove any yesterdays from the forecasts
        while self.forecasts[0]['date'] == self.today - datetime.timedelta(days=1):
            if debug:
                print '    found yesterday in forecasts -- removing it'
            self.forecasts = self.forecasts[1:]

        # then decide where we'll get today's forecast from
        # self.forecasts = self.forecasts[1:]  # uncomment to remove some of today from <self.forecasts>
        for itod in range(len(utils.times_of_day)):
            tod = utils.times_of_day[itod]
            for itmp in range(len(utils.times_of_day)):  # see if it's in the forecast  (have to loop over the first three fcasts)
                tmpfc = self.forecasts[itmp]
                if tmpfc['date'] == self.today and tmpfc['time-of-day'] == tod:
                    if debug:
                        print '    found %s today in forecasts' % tod
                    self.todays_forecast[itod] = self.forecasts.pop(itmp)  # NOTE remove this tod for today from <self.forecasts>
                    break
            if self.todays_forecast[itod][self.fcast_vals[0]] is None:  # arbitrarily use the first one to see if we found this <tod> in the forecasts
                if debug:
                    print '    couldn\'t find %s today in forecast, look in history' % tod
                for itmp in range(len(utils.times_of_day)):  # see if it's in the forecast  (have to loop over the first three fcasts)
                    tmpfc = self.todays_history[itmp]
                    if tmpfc[self.fcast_vals[0]] is not None and tmpfc['date'] == self.today and tmpfc['time-of-day'] == tod:
                        if debug:
                            print '    found %s today in history' % tod
                        self.todays_forecast[itod] = copy.deepcopy(tmpfc)
                        break

        # and then add any missing tods at the end of the forecasts
        for idate in range(len(self.expected_forecast_dates)):
            date = self.expected_forecast_dates[idate]
            if date == self.today:  # already took today out of <self.forecasts>
                continue
            for tod in utils.times_of_day:
                ifound = None
                for ifc in range(len(self.todays_forecast)):
                    fc = self.todays_forecast[ifc]
                    if date == fc['date'] and tod == fc['time-of-day']:
                        ifound = ifc
                        break
                if ifound is None:  # no forecast for this expected day
                    if idate == len(self.expected_forecast_dates) - 1 and tod == 'night':  # ah, ok, it's just the last one
                        if debug:
                            print '    missing last tod %s for %s, adding nonecast' % (tod, date)
                        self.add_empty_forecast(self.forecasts, date, tod)
                else:
                    if debug:
                        print '    found %s for %s' % (tod, date)

        # print 'HISTORY'
        # for fc in self.history:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']
        # print 'TODAYS HISTORY'
        # for fc in self.todays_history:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']
        # print 'TODAYS FORECAST'
        # for fc in self.todays_forecast:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']
        # print 'forecasts'
        # for fc in self.forecasts:
        #     print '     ', fc['date'], '  ', fc['time-of-day'][0:2], '  ', fc['high']

    # ----------------------------------------------------------------------------------------
    def write_history(self, history_fname):
        if not os.path.exists(os.path.dirname(history_fname)):
            os.makedirs(os.path.dirname(history_fname))

        # rewrite the history file, including today's forecast (which may or may not have been read from the file initially)
        with open(history_fname, 'w') as historyfile:
            writer = csv.DictWriter(historyfile, self.history_header)
            writer.writeheader()
            for fcast in self.old_history + self.history + self.todays_forecast:  # NOTE each tod in <self.todays_forecast> is taken for <self.forecasts> if possible, otherwise it's from <self.todays_history>
                if fcast[self.fcast_vals[0]] is None:  # don't write missing values
                    continue
                dcast = copy.deepcopy(fcast)
                dcast['month'] = dcast['date'].month
                dcast['day'] = dcast['date'].day
                dcast['year'] = dcast['date'].year
                del dcast['date']
                writer.writerow(dcast)

    # ----------------------------------------------------------------------------------------
    def forecast(self, args, tree, filenamestr, location_name, location_title, elevation, history_dir, htmldir):
        # print etree.tostring(tree.getroot(), pretty_print=True, method='html')
        for tr in tree.findall('.//tr'):
            keys = tr.keys()
            thlist = tr.findall('th')
            tdlist = tr.findall('td')
            if 'class' in keys and tr.get('class') == 'lar hea ':
                self.parse_days(tr)
            elif 'class' in keys and tr.get('class') == 'lar hea1':  # am/pm header
                self.parse_tods(tr)
            elif len(thlist) > 0 and thlist[0].text.strip() == 'Wind':
                self.parse_wind(tr)
            elif len(thlist) > 0 and thlist[0].text.strip() == 'Snow (':
                self.parse_simple('snow', tr, expected_units='cm')
            elif len(thlist) > 0 and thlist[0].text.strip() == 'Rain (':
                self.parse_simple('rain', tr, expected_units='mm')
            elif len(thlist) > 0 and 'High' in thlist[0].text:
                self.parse_simple('high', tr, expected_units='C')
            elif len(thlist) > 0 and 'Low' in thlist[0].text:
                self.parse_simple('low', tr, expected_units='C')
            else:
                pass

        # self.ascii(self.forecasts)
        history_fname = history_dir + '/' + filenamestr + '.csv'
        self.read_history(history_fname)
        self.combine_history_and_forecasts()  # NOTE after this, today is neither in <self.history>, nor in the <self.forecasts>
        self.write_history(history_fname)
        plotdir = htmldir + '/mtwx'
        if not os.path.exists(plotdir):
            os.makedirs(plotdir)
        daily_forecasts = self.combine_all_times_of_day(self.forecasts)
        daily_history = self.combine_all_times_of_day(self.history)
        plotting.make_mtwx_plot(args, filenamestr, location_name, location_title, int(meters_to_feet(int(elevation))), plotdir, self.todays_forecast, self.forecasts, daily_history, daily_forecasts)
