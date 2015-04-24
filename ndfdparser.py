#!/usr/bin/env python
import sys
import os
from datetime import datetime, timedelta
from subprocess import check_call, CalledProcessError
from xml.etree import ElementTree as ET
import csv

weekdays = ('Mon', 'Tues', 'Wed', 'Thurs', 'Fri', 'Sat', 'Sun')

# ----------------------------------------------------------------------------------------
def parse_noaa_time_string(noaa_time_str):
    date_str, time_str = noaa_time_str.split('T')  # will raise ValueError if it doesn't split into two pieces
    tzhackdelta = None
    if '-' in time_str:
        time_str, tzinfo_str = time_str.split('-')  # ignoring time zone info for now
    elif time_str[-1] == 'Z':
        print 'HACK subtracting eight hours from GMT'
        tzhackdelta = timedelta(hours=-8)
        time_str = time_str[:-1]
    year, month, day = [ int(val) for val in date_str.split('-') ]
    hour, minute, second = [ int(val) for val in time_str.split(':') ]
    moment = datetime(year, month, day, hour, minute, second)
    if tzhackdelta is not None:
        moment += tzhackdelta
    return moment

# ----------------------------------------------------------------------------------------
def get_time_layouts(root):
    layouts = {}
    for lout in root.find('data').findall('time-layout'):
        name = lout.find('layout-key').text
        layouts[name] = {'start':[], 'end':[]}
        for start_end in ('start', 'end'):
            for tmptime in lout.iter(start_end + '-valid-time'):
                moment = parse_noaa_time_string(tmptime.text)
                layouts[name][start_end].append(moment)
    return layouts

# ----------------------------------------------------------------------------------------
def combine_days(action, pdata, debug=False):
    """ 
    Perform <action> for all the values within each day, where <action> is either sum or mean.
    """
    assert action == 'sum' or action == 'mean'

    starts, ends, values, weight_sum = [], [], [], []

    # ----------------------------------------------------------------------------------------
    def get_time_delta_in_hours(start, end):
        """ NOTE assumes no overflows or wraps or nothing """
        dhour = end.hour - start.hour
        dmin = end.minute - start.minute
        dsec = end.second - start.second
        dtime = timedelta(hours=dhour, minutes=dmin, seconds=dsec)  # NOTE rounds to nearest second
        # print start, end, dtime
        return float(dtime.seconds) / (60.*60.)
    # ----------------------------------------------------------------------------------------
    def add_new_day(dstart, dend, dval):
        weight = '-'
        starts.append(dstart)
        ends.append(dend)
        if action == 'sum':
            values.append(dval)
        elif action == 'mean':
            weight = float(get_time_delta_in_hours(dstart, dend))
            values.append(weight*dval)
            weight_sum.append(weight)
        else:
            raise Exception('invalid action'+action)
        if debug:
            print '    new day', dstart, dend, weight, dval
    # ----------------------------------------------------------------------------------------
    def increment_day(dstart, dend, dval):
        ends[-1] = dend
        weight = '-'
        if action == 'sum':
            values[-1] += dval
        elif action == 'mean':
            weight = float(get_time_delta_in_hours(dstart, dend))
            values[-1] += weight * dval
            weight_sum[-1] += weight
        else:
            raise Exception('invalid action'+action)
        if debug:
            print '    increment', starts[-1], dend, weight, dval, '   ', values[-1]
    # ----------------------------------------------------------------------------------------
    def incorporate_value(istart, iend, ival):
        # if debug:
        #     print '    incorporate', istart, iend, ival
        if len(values) == 0 or ends[-1].day != istart.day:
            add_new_day(istart, iend, ival)
        else:
            increment_day(istart, iend, ival)

    for ival in range(len(pdata['values'])):
        start = pdata['time-layout']['start'][ival]
        if len(pdata['time-layout']['end']) > 0:  # some of them only have start times
            end = pdata['time-layout']['end'][ival]
        elif len(pdata['time-layout']['start']) > ival+1:  # so use the next start time minus a ms if we can
            end = pdata['time-layout']['start'][ival+1] - timedelta(milliseconds=-1)
        else:
            end = pdata['time-layout']['start'][ival] + timedelta(hours=6)  # otherwise just, hell, add six hours
        if debug:
            print ' day %3d-%-3d  hour %3d-%-3d     %s' % (start.day, end.day, start.hour, end.hour, pdata['values'][ival])

        # skip null values (probably from cloud cover)
        if pdata['values'][ival] == None:
            if debug:
                print '    skipping null value'
            continue

        val = float(pdata['values'][ival])
        if start.day == end.day:
            incorporate_value(start, end, val)
        else:
            if debug:
                print '       start (%s) and end (%s) days differ' % (start, end)
            # print start, end
            # assert start.day + 1 == end.day  # for now only handle the case where they differ by one day
            midnight = datetime(year=end.year, month=end.month, day=end.day, hour=0, minute=0, second=0)
            if action == 'sum':
                hours_before = get_time_delta_in_hours(start, midnight)  #24 - start.hour
                hours_after = get_time_delta_in_hours(midnight, end)  #end.hour
                val_before = val * float(hours_before) / (hours_before + hours_after)
                val_after = val * float(hours_after) / (hours_before + hours_after)
                if debug:
                    print '        apportioning between',
                    print 'first %f * %f / (%f + %f) = %f' % (val, hours_before, hours_before, hours_after, val_before),
                    print 'and second %f * %f / (%f + %f) = %f' % (val, hours_after, hours_before, hours_after, val_after)
            else:
                val_before, val_after = val, val
            incorporate_value(start, midnight + timedelta(milliseconds=-1), val_before)  #start + timedelta(hours=24-start.hour, milliseconds=-1), val_before)
            incorporate_value(midnight, end + timedelta(milliseconds=-1), val_after)  # end - timedelta(hours=end.hour), end, val_after)

    dailyvals = {}
    for ival in range(len(values)):
        dailyvals[int(starts[ival].day)] = values[ival]
        if action == 'mean':
            # if debug:
            #     print 'total', get_time_delta_in_hours(starts[ival], ends[ival])
            dailyvals[int(starts[ival].day)] /= weight_sum[ival]  #get_time_delta_in_hours(starts[ival], ends[ival])

    if debug:
        print '  final:'
        for key in sorted(dailyvals.keys()):
            print '    ', key, dailyvals[key]
    return dailyvals

# ----------------------------------------------------------------------------------------
def parse_data(root, time_layouts, debug=False):
    pars = root.find('data').find('parameters')
    data = {}
    for vardata in pars:
        # first figure out the name
        all_names = list(vardata.iter('name'))
        if len(all_names) != 1:
            raise Exception('ERROR too many names for %s: %s' % (vardata.tag, ', '.join(all_names)))
        name = all_names[0].text
        if name in data:
            raise Exception('ERROR %s already in data' % key)

        # then get the data
        data[name] = {}
        if vardata.get('time-layout') is None:  # single-point data
            if debug:
                print '  no layout %s' % name
            continue
        else:  # time series data
            data[name]['time-layout'] = time_layouts[vardata.get('time-layout')]
            if name == 'Conditions Icons':
                data[name]['values'] = [ val.text for val in vardata.findall('icon-link') ]
            else:
                data[name]['values'] = [ val.text for val in vardata.findall('value') ]
            if debug:
                print 'added %s (%s)' % (name, vardata.get('time-layout'))
            if len(data[name]['time-layout']['start']) != len(data[name]['values']):
                if debug:
                    print '  time layout different length for %s' % name
                else:
                    pass

    return data

# ----------------------------------------------------------------------------------------
def find_min_temp(pdata, prev_day, next_day):
    """ find min temp for the night of <prev_day> to <next_day> """
    for ival in range(len(pdata['values'])):
        start = pdata['time-layout']['start'][ival]
        end = pdata['time-layout']['end'][ival]
        if start.day == prev_day and end.day == next_day:
            return int(pdata['values'][ival])
    # raise Exception('ERROR didn\'t find min temp for night of %d-%d in %s' % (prev_day, next_day, pdata['time-layout']))
    return None

# ----------------------------------------------------------------------------------------
def find_max_temp(pdata, day):
    """ find min temp for the night of <prev_day> to <next_day> """
    for ival in range(len(pdata['values'])):
        start = pdata['time-layout']['start'][ival]
        end = pdata['time-layout']['end'][ival]
        if start.day == day and end.day == day:
            return int(pdata['values'][ival])
    # raise Exception('ERROR didn\'t find max temp for %d in %s' % (day, pdata['time-layout']))
    return None

# ----------------------------------------------------------------------------------------
def find_icon_for_time(day, hour, icondata):
    # print 'look: %d %d' % (day, hour)
    closest_icon_url = None  # url corresponding to nearest time
    closest_hour = None
    for i in range(len(icondata['time-layout']['start'])):
        time = icondata['time-layout']['start'][i]
        # print time
        if time.day != day:  # not even the right day
            continue
        if closest_icon_url is None or abs(time.hour - hour) < abs(closest_hour - hour):
            closest_icon_url = icondata['values'][i]
            closest_hour = time.hour
            clday = time.day

    # print '  using %s at day %d hour %d' % (closest_icon_url, clday, closest_hour)
    return closest_icon_url  # can be None

# ----------------------------------------------------------------------------------------
def get_history(history_fname):
    n_max_days = 5

    if not os.path.exists(history_fname):
        return None
    fileinfo = {}
    with open(history_fname, 'r') as historyfile:
        reader = csv.DictReader(historyfile)
        for line in reader:
            key = datetime(int(line['year']), int(line['month']), int(line['day']))
            now = datetime.now()
            rounded_now = datetime(now.year, now.month, now.day)
            if (key - rounded_now).days >= 0:  # entry is in the future (or is today)
                continue
            fileinfo[key] = line

    history = {'days' : [], 'hi' : [], 'lo' : [], 'liquid' : [], 'snow' : []}
    found_one_day = False
    for iday in range(n_max_days):
        day = datetime.now() - timedelta(n_max_days - iday)
        history['days'].append(day.day)
        key = datetime(day.year, day.month, day.day)
        if key in fileinfo:
            found_one_day = True
            history['hi'].append(float(fileinfo[key]['hi']))
            history['lo'].append(float(fileinfo[key]['lo']))
            history['liquid'].append(float(fileinfo[key]['liquid']))
            history['snow'].append(float(fileinfo[key]['snow']) / 12.)
        else:
            history['hi'].append(None)
            history['lo'].append(None)
            history['liquid'].append(None)
            history['snow'].append(None)

    if not found_one_day:
        return None
    return history

# ----------------------------------------------------------------------------------------
def make_history_plot(location_name, htmldir):
    if not os.path.exists(htmldir + '/history'):
        os.makedirs(htmldir + '/history')
    history = get_history(htmldir + '/history/' + location_name + '.csv')
    if history is None:
        return None

    import matplotlib as mpl
    mpl.use('Agg')
    import matplotlib.pyplot as plt
    nxbins = 5
    nybins = 2
    
    fsize = 40
    mpl.rcParams.update({
        'figure.autolayout': True,  # doesn't *##*$@!ing do anything
        # 'font.size': fsize,
        'font.family': 'serif',
        'font.weight': 'bold',
        'legend.fontsize': fsize,
        'axes.titlesize': fsize,
        # 'axes.labelsize': fsize,
        'xtick.labelsize': fsize,
        'ytick.labelsize': fsize,
        'axes.labelsize': fsize
    })

    fig, ax1 = plt.subplots()
    fig.set_size_inches(8, 5)
    lo_color = '#99B2FF'
    hi_color = 'red'
    plt.locator_params(nbins=nxbins, axis='x')
    plt.locator_params(nbins=nybins, axis='y')

    ax2 = ax1.twinx()
    liquid_color = '#1947D1'
    snow_color = 'grey'

    # figliquid = ax2.plot(history['days'], history['liquid'], color=liquid_color, linewidth=3)
    # figliquid = ax2.plot(history['days'], history['snow'], color=snow_color, linewidth=3)

    liquid_hist, liquid_weights = [], []
    snow_hist, snow_weights = [], []
    for iday in range(len(history['days'])):
        day = history['days'][iday]
        if history['liquid'][iday] is not None:
            for il in range(int(1000*history['liquid'][iday])):
                liquid_hist.append(day)
                liquid_weights.append(1./1000)
        if history['snow'][iday] is not None:
            for il in range(int(1000*history['snow'][iday])):
                snow_hist.append(day)
                snow_weights.append(1./1000)
    ax2.hist(liquid_hist, bins=len(history['days']), range=(history['days'][0]-.6, history['days'][-1]+.4), weights=liquid_weights, rwidth=.5, color=liquid_color, alpha=0.5)
    ax2.hist(snow_hist, bins=len(history['days']), range=(history['days'][0]-.4, history['days'][-1]+.6), weights=snow_weights, rwidth=.5, color=snow_color, alpha=0.5)

    fighi = ax1.plot(history['days'], history['hi'], color=hi_color, linewidth=5)
    figlo = ax1.plot(history['days'], history['lo'], color=lo_color, linewidth=5)

    plt.locator_params(nbins=nxbins, axis='x')
    plt.locator_params(nbins=nybins, axis='y')
    plt.gcf().subplots_adjust(bottom=0.11, left=0.11, right=0.87, top=0.87)
    plt.xlim(history['days'][0] - 0.25, history['days'][-1] + 0.25)

    y2min, y2max = ax2.get_ylim()
    xmin, xmax = ax2.get_xlim()
    fig.text(0.88, 0.95, 'in.', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.93, 0.95, 'ft.', color=snow_color, fontsize=20, alpha=0.5)
    fig.text(0.01, 0.95, 'deg F', color='black', fontsize=20)
    fig.text(0.02, 0.72, 'hi', color=hi_color, fontsize=20)
    fig.text(0.02, 0.67, 'lo', color=lo_color, fontsize=20)
    fig.text(0.88, 0.72, 'liquid', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.88, 0.67, 'snow', color=snow_color, fontsize=20, alpha=0.5)
    plt.suptitle(location_name, fontsize=20)

    plotfname = htmldir + '/history/' + location_name + '.png'
    plt.savefig(plotfname)
    return plotfname

# ----------------------------------------------------------------------------------------
def write_tomorrows_history(history_fname, tomorrow, tmax, tmin, liquid, snow, wind):
    rounded_tomorrow = datetime(tomorrow.year, tomorrow.month, tomorrow.day)  # no hours and minutes and whatnot

    history = {}
    history_header = ('month', 'day', 'year', 'hi', 'lo', 'liquid', 'snow', 'wind')
    if os.path.exists(history_fname):  # read in any existing history
        with open(history_fname, 'r') as historyfile:
            reader = csv.DictReader(historyfile)
            for line in reader:
                key = datetime(int(line['year']), int(line['month']), int(line['day']))
                history[key] = line

    # tomorrow = datetime.now() + timedelta(days=1)
    # if rounded_tomorrow in history:
    #     print 'replacing'
    history[rounded_tomorrow] = {'month' : tomorrow.month,
                                 'day' : tomorrow.day,
                                 'year' : tomorrow.year,
                                 'hi' : tmax,
                                 'lo' : tmin,
                                 'liquid' : liquid,
                                 'snow' : snow,
                                 'wind' : wind}
    with open(history_fname, 'w') as historyfile:
        writer = csv.DictWriter(historyfile, history_header)
        writer.writeheader()
        for line in history.values():
            writer.writerow(line)

# ----------------------------------------------------------------------------------------
def get_html(args, data, location_name, htmldir, ndays=5, debug=False):
    liquid = combine_days('sum', data['Liquid Precipitation Amount'])
    snow = combine_days('sum', data['Snow Amount'])
    wind_speed = combine_days('mean', data['Wind Speed'])
    cloud = combine_days('mean', data['Cloud Cover Amount'])
    percent_precip = combine_days('mean', data['12 Hourly Probability of Precipitation'])

    txtvals = {'days':[], 'tmax':[], 'tmin':[], 'liquid':[], 'snow':[], 'wind':[], 'cloud':[], 'precip':[]}
    if debug:
        print '%-5s    %4s   %5s%5s   %5s  %5s' % ('', 'hi lo', 'precip (snow)', '%', 'wind', 'cloud')
    rowlist = []

    history_plotname = make_history_plot(location_name, htmldir)
    if args.no_history:
        pass
    elif history_plotname is None:
        rowlist.append('n/a')
    else:
        rowlist.append('<a target="_blank" href="' + history_plotname + '"><img  src="' + history_plotname + '" alt="weather" width="120" height="75">')
        
    for iday in range(ndays):
        day = datetime.now() + timedelta(days=iday)
    
        tmax = find_max_temp(data['Daily Maximum Temperature'], day.day)
        tmin = find_min_temp(data['Daily Minimum Temperature'], day.day, (day + timedelta(days=1)).day)

        if iday == 1:  # tomorrow (i.e. the soonest complete day for which we have a forecast)
            write_tomorrows_history(htmldir + '/history/' + location_name + '.csv', day, tmax, tmin, liquid.get(day.day, None), snow.get(day.day, None), wind_speed.get(day.day, None))

        icon_url = find_icon_for_time(day.day, 12, data['Conditions Icons'])  # find icon for noon this day
        icon_url = icon_url.replace('http://forecast.weather.gov/images/wtf', 'http://www.nws.noaa.gov/weather/images/fcicons')  # some of the images seem to not be at the orignal url, but if you google them...
        if icon_url is not None:
            icon_file = os.path.basename(icon_url)
            if not os.path.exists(htmldir + '/images'):
                os.makedirs(htmldir + '/images')
            if not os.path.exists(htmldir + '/images/' + icon_file):
                print 'downloading %s' % icon_url
                try:
                    check_call(['wget', '-q', '-O', htmldir + '/images/' + icon_file, icon_url])
                except CalledProcessError:
                    print 'ERROR ' + icon_file + ' not found at ' + icon_url
                    
        else:
            icon_file = 'missing.jpg'

        row = ''
        if tmax is not None:
            row += '<font color=red>'
            row += '<b>%d</b><font size=1>F</font>' % tmax
            row += '</font>'
        else:
            row += '&nbsp&nbsp&nbsp'
        # row += '&nbsp&nbsp&nbsp&nbsp'
        row += '&nbsp&nbsp<img  src="images/' + icon_file + '" alt="weather" width="28" height="28">&nbsp&nbsp'
        if tmin is not None:
            row += '<font color=#99B2FF>'
            row += '<b>%d</b><font size=1>F</font>' % tmin
            row += '</font>'
        else:
            row += '&nbsp&nbsp&nbsp'
        row += '<br>'

        # precip
        if day.day in percent_precip:
            row += '<b> %.0f</b><font size=1>%%</font>' % percent_precip[day.day]

        # liquid
        row += '<font color=#1947D1><b>'
        if day.day in liquid:
            if liquid[day.day] > 0.0:
                row += ('&nbsp%.2f"' % liquid[day.day]).replace('0.', '.')
            else:
                row += '&nbsp0"'
        else:
            row += '&nbsp-&nbsp'
        row += '</b></font>'

        # snow
        row += '<font color=grey size=1><b>'
        if day.day in liquid:
            if snow[day.day] > 0.0:
                row += (' (<b>%.0f"</b>)' % snow[day.day]).replace('0.', '.')
            else:
                row += ''
        else:
            row += '&nbsp<b>-</b>&nbsp'
        row += '</font>'

        row += '<br>'

        # wind speed
        if day.day in wind_speed:
            row += '<b>%.0f</b>' % wind_speed[day.day]
            row += '<font size=1>mph    </font>'
        else:
            row += ' - '
        
        # cloud cover
        if day.day in cloud:
            row += '&nbsp<b>%.0f</b>' % cloud[day.day]
            row += '<font size=1>%cloud</font>'
        else:
            row += '&nbsp&nbsp&nbsp- '
        
        rowlist.append(row)

        tv = txtvals
        tv['tmax'].append('-' if tmax is None else tmax)
        tv['tmin'].append('-' if tmin is None else tmin)
        tv['liquid'].append(('%5.1f' % liquid[day.day]) if day.day in liquid else '-')
        tv['snow'].append('')
        if day.day in snow and snow[day.day] > 0.0:
            tv['snow'][-1] = '%5.1f' % snow[day.day]
        tv['wind'].append(('%5.0f' % wind_speed[day.day]) if day.day in wind_speed else '-')
        tv['cloud'].append(('%5.0f' % cloud[day.day]) if day.day in cloud else '-')
        tv['precip'].append(('%5.0f' % percent_precip[day.day]) if day.day in percent_precip else '-')
        tv['days'].append(weekdays[day.weekday()])
        if debug:
            print '%-6s %4s %-3s  %5s  %5s %5s   %5s  %5s' % (weekdays[day.weekday()], tv['tmax'][-1], tv['tmin'][-1], tv['liquid'][-1], tv['snow'][-1], tv['precip'][-1], tv['wind'][-1], tv['cloud'][-1])

    return tv, rowlist

# ----------------------------------------------------------------------------------------
def forecast(args, tree, location_name, htmldir):
    root = tree.getroot()
    time_layouts = get_time_layouts(root)
    data = parse_data(root, time_layouts)
    point = root.find('data').find('location').find('point')
    lat, lon = point.get('latitude'), point.get('longitude')
    tv, rowlist = get_html(args, data, location_name, htmldir, debug=True)
    point_forecast_url = list(root.iter('moreWeatherInformation'))[0].text
    rowlist.insert(0, '<a href="' + point_forecast_url + '">LOCATION</a>')

    return tv['days'], rowlist
