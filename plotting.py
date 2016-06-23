import os
import sys
import math
import numpy
import datetime

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import gridspec

import utils

def make_wind_plot(axwind, combined_forecasts, fake_date_range, total_width, total_height, height_ratios, wind_color):
    max_wind = 60  # NOTE this doesn't saturate when you get this high, it's just that the arrow starts overflowing its allotted space
    axwind.set_xlim(0., 1.)
    axwind.set_ylim(-0.5, 0.5)
    xwidth = 1. / len(combined_forecasts)  # distance between forecasts
    for ifc in fake_date_range:
        fc = combined_forecasts[ifc]
        xpos = 0.5 * xwidth + float(ifc) / len(combined_forecasts)  # center of this forecast
        if fc['wind-speed'] is None:
            axwind.text(xpos, -.4, 'n/a', color=wind_color, fontsize=20)
            continue
        arrow_length = 0.9 * xwidth * fc['wind-speed'] / max_wind
        # slope = float(ifc) / len(combined_forecasts)
        # theta = math.atan(slope)
        theta = fc['wind-direction'] if fc['wind-direction'] is not None else math.pi / 2  #2 * math.pi * float(ifc) / len(combined_forecasts)
        dx = arrow_length * math.cos(theta)
        dy = (total_width / total_height) * height_ratios * arrow_length * math.sin(theta)
        # print xpos, theta, dx, dy
        # axwind.arrow(xpos, 0., dx, dy)  #, head_width=0.05, head_length=0.1, fc='k', ec='k')
        axwind.plot([xpos - dx/2, xpos + dx/2], [0. - dy/2, dy/2], linewidth=12, color=wind_color)
        axwind.plot(xpos + dx/2, 0. + dy/2, marker=(3, 0, theta * 180. / math.pi - 90.), markersize=28, linestyle='None', color=wind_color)
        # axwind.text(xpos, 0., utils.wind_angles[utils.wind_directions.index(fc['wind-direction'])], color=wind_color, fontsize=20)
        axwind.text(xpos, -.4, '%.0f' % round(fc['wind-speed'], -1), color=wind_color, fontsize=20)
    axwind.set_axis_off()
    axwind.text(-.03, -.3, 'mph', color=wind_color, fontsize=20)

# ----------------------------------------------------------------------------------------
def make_combined_noaa_plot(args, location_name, elevation, htmldir, history, todays_forecast, forecasts):
    if not os.path.exists(htmldir + '/noaa'):
        os.makedirs(htmldir + '/noaa')

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


    fig = plt.figure()
    height_ratios = 4
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, height_ratios]) 
    gs.update(hspace=0.05) # set the spacing between axes. 
    axwind = plt.subplot(gs[0])
    ax1 = plt.subplot(gs[1])

    total_aspect = 2.94
    total_width = 25.
    total_height = total_width / total_aspect
    # total_width = 25
    # total_height = 8.5
    fig.set_size_inches(total_width, total_height)

    lo_color = '#99B2FF'
    hi_color = 'red'
    # plt.locator_params(nbins=nxbins, axis='x')
    # plt.locator_params(nbins=nybins, axis='y')
    combined_forecasts = {}
    for var in todays_forecast:
        if var is None:  # not sure what this is doing in there
            continue
        if var == 'days' or var == 'percent-cloud' or var == 'percent-precip':
            continue
        combined_forecasts[var] = todays_forecast[var] + forecasts[var]
        if history is not None:
            combined_forecasts[var] = history[var] + combined_forecasts[var]

    ax2 = ax1.twinx()
    liquid_color = '#1947D1'
    snow_color = 'grey'

    n_days = len(combined_forecasts['dates'])

    # for iday in range(len(combined_forecasts['dates'])):
    #     print '%4d  %5s    %8.1f   %8.1f'  % (iday, combined_forecasts['dates'][iday].day, combined_forecasts['hi'][iday], combined_forecasts['lo'][iday])

    liquid_hist, liquid_weights = [], []
    snow_hist, snow_weights = [], []
    n_big_number = 5e2
    for iday in range(n_days):
        # liquid
        if combined_forecasts['liquid'][iday] is None:
            liquid_hist.append(iday)
            liquid_weights.append(1./n_big_number)
        else:
            total_liquid_precip = combined_forecasts['liquid'][iday]
            if combined_forecasts['snow'][iday] is not None:  # HACK subtract off a rough approximation of how much is falling as snow -- snowfall is in feet, and a foot is about an inch of liquid precip... right?
                total_liquid_precip = max(0., total_liquid_precip - combined_forecasts['snow'][iday])
            for il in range(int(n_big_number*total_liquid_precip) + 1):  # NOTE this gives you 1./n_big_number instead of zero
                liquid_hist.append(iday)
                liquid_weights.append(1./n_big_number)

        # snow
        if combined_forecasts['snow'][iday] is None:
            snow_hist.append(iday)
            snow_weights.append(1./n_big_number)
        else:
            for il in range(int(n_big_number*combined_forecasts['snow'][iday]) + 1):  # NOTE this gives you 1./n_big_number instead of zero
                snow_hist.append(iday)
                snow_weights.append(1./n_big_number)

    # date_range = range(combined_forecasts['days'][0], combined_forecasts['days'][0] + n_days)
    fake_date_range = range(n_days)

    if len(liquid_hist) == 0:
        raise Exception('liquid hist data has length zero')
    if len(snow_hist) == 0:
        raise Exception('snow hist data has length zero')
    ax2.hist(liquid_hist, bins=n_days, range=(fake_date_range[0]-.6, fake_date_range[-1]+.4), weights=liquid_weights, rwidth=.5, color=liquid_color, alpha=0.5)  #, hatch='//')
    ax2.hist(snow_hist, bins=n_days, range=(fake_date_range[0]-.4, fake_date_range[-1]+.6), weights=snow_weights, rwidth=.5, color=snow_color, alpha=0.5)

    fighi = ax1.plot(fake_date_range, combined_forecasts['hi'], color=hi_color, linewidth=5)
    figlo = ax1.plot(fake_date_range, combined_forecasts['lo'], color=lo_color, linewidth=5)

    plt.gcf().subplots_adjust(bottom=0.1, left=0.05, right=0.93, top=0.92)
    plt.xlim(fake_date_range[0] - 0.25, fake_date_range[-1] + 0.25)

    xticks, xticklabels = [], []
    today = datetime.date.today()
    itoday = None
    for ifc in fake_date_range:
        xticks.append(ifc)
        if history is not None and ifc < len(history['dates']):
            if ifc == int(len(history) / 2) - 1:  # near the middle of the history
                label = 'last %d days' % len(history['dates'])
            else:
                label = ''
        elif combined_forecasts['dates'][ifc] == today:
            itoday = ifc
            label = 'today'
        else:
            label = utils.weekdays[combined_forecasts['dates'][ifc].weekday()]
        snow = combined_forecasts['snow'][ifc] if combined_forecasts['snow'][ifc] is not None else -1.
        # print '%3d   %s  %5.1f   %s' % (ifc, combined_forecasts['dates'][ifc], snow, label)
        xticklabels.append(label)

    plt.xticks(xticks)
    ax2.set_xticklabels(xticklabels)

    mintemp = min(t for t in combined_forecasts['lo'] if t is not None)
    maxtemp = max(t for t in combined_forecasts['hi'] if t is not None)
    minprecip = min(p for p in combined_forecasts['liquid'] + combined_forecasts['snow'] if p is not None)  # snow's already been converted to feet
    maxprecip = max(p for p in combined_forecasts['liquid'] + combined_forecasts['snow'] if p is not None)

    modulo = 5.
    mintemp = int(math.floor(mintemp / modulo)) * modulo
    maxtemp = int(math.ceil(maxtemp / modulo)) * modulo
    ax1.set_ylim(mintemp, maxtemp)

    ax1.yaxis.set_ticks([mintemp, int(mintemp + 0.5*(maxtemp-mintemp)), maxtemp])
    if maxprecip >= 0.5:
        modulo = 1.
        minprecip = int(math.floor(minprecip / modulo)) * modulo
        maxprecip = int(math.ceil(maxprecip / modulo)) * modulo
        ax2.set_ylim(minprecip, max(0.5, maxprecip))
        ax2.yaxis.set_ticks([minprecip, minprecip + 0.5*(maxprecip-minprecip), maxprecip])
        ax2.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter('%.1f'))
    else:
        modulo = 0.5
        minprecip = int(math.floor(minprecip / modulo)) * modulo
        maxprecip = int(math.ceil(maxprecip / modulo)) * modulo
        ax2.set_ylim(minprecip, max(0.5, maxprecip))

        ax2.yaxis.set_ticks([minprecip, minprecip + 0.5*(maxprecip-minprecip), maxprecip])
        ax2.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter('%.2f'))

    # lines emphasizing location of today and tomorrow
    ax1.plot([itoday - 0.5, itoday - 0.5], [mintemp, 0.9*maxtemp], color='black', linestyle='--', linewidth=3)
    ax1.plot([itoday + 0.5, itoday + 0.5], [mintemp, 0.9*maxtemp], color='black', linestyle='--', linewidth=3)
    # freezing level line
    ax1.plot([-0.2, 7./8 * len(fake_date_range)], [utils.freezing_point, utils.freezing_point], color='blue', linestyle='--', linewidth=1)
    # ax1.plot([-0.2, len(fake_date_range) / 4.], [32., 32.], color='blue', linestyle='--', linewidth=1)
    # ax1.plot([3./4 * len(fake_date_range), len(fake_date_range)], [32., 32.], color='blue', linestyle='--', linewidth=1)

    for iday in range(len(forecasts['dates'])):
        if forecasts['liquid'][iday] is None:
            history_len = 0 if history is None else len(history['dates'])
            xpos = float(iday + history_len + 1) / len(combined_forecasts['dates']) - 0.03
            fig.text(xpos, 0.21, '%.0f%% precip' % forecasts['percent-precip'][iday], color='blue', fontsize=20, alpha=0.5)
            fig.text(xpos, 0.15, '%.0f%% cloud' % forecasts['percent-cloud'][iday], color='black', fontsize=20, alpha=0.5)

    ax1.spines['top'].set_visible(False)
    ax1.get_xaxis().tick_bottom()

    # fig.text(0.935, 0.62, 'precip\ntotal (in)', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.935, 0.62, 'rain (in)', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.935, 0.57, 'snow (ft)', color=snow_color, fontsize=20, alpha=0.5)
    fig.text(0.003, 0.6, 'deg F', color='black', fontsize=20)
    fig.text(0.02, 0.3, 'hi', color=hi_color, fontsize=20)
    fig.text(0.02, 0.25, 'lo', color=lo_color, fontsize=20)
    plt.suptitle(location_name + '   (' + str(int(round(elevation, -2))) + ' ft)', fontsize=20)

    forecasts_for_wind = []
    wind_color = 'green'
    for iday in range(len(combined_forecasts['dates'])):
        forecasts_for_wind.append({'wind-speed' : combined_forecasts['wind'][iday], 'wind-direction' : None})
    make_wind_plot(axwind, forecasts_for_wind, fake_date_range, total_width, total_height, height_ratios, wind_color)

    plotfname = htmldir + '/noaa/' + location_name + '.svg'
    plt.savefig(plotfname)
    plt.close()
    return plotfname.replace(htmldir + '/', '')

# ----------------------------------------------------------------------------------------
def make_hists(forecasts, varname):
    hist, weights = [], []
    n_big_number = 5e2
    for ifc in range(len(forecasts)):
        fcast = forecasts[ifc]
        if fcast[varname] is None:  # missing forecast
            continue
        for il in range(int(n_big_number*float(fcast[varname])) + 1):  # NOTE this gives you 1./n_big_number instead of zero
            hist.append(ifc)
            weights.append(1./n_big_number)

    return hist, weights

# ----------------------------------------------------------------------------------------
def make_mtwx_plot(args, filenamestr, location_name, location_title, elevation, plotdir, todaycast, forecasts, daily_history, daily_forecasts):
    """ NOTE this has a *lot* of overlap with the noaa function, but hopefully not enough to justify merging them """
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
        'xtick.labelsize': 0.9*fsize,
        'ytick.labelsize': 0.8*fsize,
        'axes.labelsize': fsize
    })

    # fig, axes = plt.subplots(nrows=2, height_ratios=[1,3])
    # ax1 = axes[1]
    fig = plt.figure()
    height_ratios = 4
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, height_ratios]) 
    gs.update(hspace=0.05) # set the spacing between axes. 
    axwind = plt.subplot(gs[0])
    ax1 = plt.subplot(gs[1])
    # ax1 = plt.subplot(gs[1])

    total_width = 25
    total_height = 8.5
    fig.set_size_inches(total_width, total_height)
    lo_color = '#99B2FF'
    hi_color = 'red'
    wind_color = 'green'
    # plt.locator_params(nbins=nxbins, axis='x')
    # plt.locator_params(nbins=nybins, axis='y')

    # ----------------------------------------------------------------------------------------
    # temp and precip
    ax2 = ax1.twinx()
    rain_color = '#1947D1'
    snow_color = 'grey'

    tomorrowcast = forecasts[0:3]
    dayaftertomorrowcast = forecasts[3:6]

    combined_forecasts = daily_history + todaycast + tomorrowcast + dayaftertomorrowcast + daily_forecasts[2:]
    # for ifc in range(1, len(combined_forecasts)):
    #     print combined_forecasts[ifc-1]['date']
    #     # assert combined_forecasts[ifc-1]['date'] + datetime.timedelta(days=1) == combined_forecasts[ifc]['date']
    # sys.exit()
    rain_hist, rain_weights = make_hists(combined_forecasts, 'rain')
    snow_hist, snow_weights = make_hists(combined_forecasts, 'snow')

    fake_date_range = range(len(combined_forecasts))

    # daily_forecasts_after_tomorrow = daily_forecasts[2:]  # remove today and tomorrow
    ax2.hist(rain_hist, bins=len(combined_forecasts), range=(fake_date_range[0]-.6, fake_date_range[-1]+.4), weights=rain_weights, rwidth=.5, color=rain_color, alpha=0.5)
    ax2.hist(snow_hist, bins=len(combined_forecasts), range=(fake_date_range[0]-.4, fake_date_range[-1]+.6), weights=snow_weights, rwidth=.5, color=snow_color, alpha=0.5)

    fighi = ax1.plot(fake_date_range, [fc['high'] for fc in combined_forecasts], color=hi_color, linewidth=5)
    figlo = ax1.plot(fake_date_range, [fc['low'] for fc in combined_forecasts], color=lo_color, linewidth=5)

    plt.gcf().subplots_adjust(bottom=0.1, left=0.05, right=0.93, top=0.92)
    plt.xlim(fake_date_range[0] - 0.25, fake_date_range[-1] + 0.25)

    xticks, xticklabels = [], []
    today = datetime.date.today()
    itoday = None
    imissing = []
    for ifc in fake_date_range:
        fc = combined_forecasts[ifc]
        # print '%4d  %5s    %8.2f   %8.1f' % (ifc, fc['date'].day, fc['snow'], fc['wind-speed'])
        xticks.append(ifc)
        if fc['rain'] is None or fc['snow'] is None:  # hopefully either all or none of them are None. I should kinda test each individually
            imissing.append(ifc)
        if ifc < len(daily_history):
            if ifc == int(len(daily_history) / 2) - 1:  # near the middle of the history
                label = 'last %d days' % len(daily_history)
            else:
                label = ''
        elif fc['date'] == today:  # today
            if fc['time-of-day'] == 'AM':
                label = ''
            elif fc['time-of-day'] == 'PM':
                itoday = ifc
                label = 'today'
            elif fc['time-of-day'] == 'night':
                label = ''
        elif fc['date'] == today + datetime.timedelta(days=1) or fc['date'] == today + datetime.timedelta(days=2):  # tomorrow or the next day
            if fc['time-of-day'] == 'AM':
                label = ''
            elif fc['time-of-day'] == 'PM':
                label = utils.weekdays[fc['date'].weekday()]
            elif fc['time-of-day'] == 'night':
                label = ''
            else:
                assert False
        else:
            label = utils.weekdays[fc['date'].weekday()]
        xticklabels.append(label)

    plt.xticks(xticks)
    ax2.set_xticklabels(xticklabels)

    mintemp = min(t for t in [fc['low'] for fc in combined_forecasts] if t is not None)
    maxtemp = max(t for t in [fc['high'] for fc in combined_forecasts] if t is not None)
    minprecip, maxprecip = None, None
    for fc in combined_forecasts:
        if fc['rain'] is None or fc['snow'] is None:
            continue
        precip = fc['rain'] + fc['snow']
        if minprecip is None or precip < minprecip:
            minprecip = precip
        if maxprecip is None or precip > maxprecip:
            maxprecip = precip

    modulo = 5.
    mintemp = int(math.floor(mintemp / modulo)) * modulo
    maxtemp = int(math.ceil(maxtemp / modulo)) * modulo
    ax1.set_ylim(mintemp, maxtemp)

    ax1.yaxis.set_ticks([mintemp, int(mintemp + 0.5*(maxtemp-mintemp)), maxtemp])
    if maxprecip >= 0.5:
        modulo = 1.
        minprecip = int(math.floor(minprecip / modulo)) * modulo
        maxprecip = int(math.ceil(maxprecip / modulo)) * modulo
        ax2.set_ylim(minprecip, max(0.5, maxprecip))
        ax2.yaxis.set_ticks([minprecip, minprecip + 0.5*(maxprecip-minprecip), maxprecip])
        ax2.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter('%.1f'))
    else:
        modulo = 0.5
        minprecip = int(math.floor(minprecip / modulo)) * modulo
        maxprecip = int(math.ceil(maxprecip / modulo)) * modulo
        ax2.set_ylim(minprecip, max(0.5, maxprecip))

        ax2.yaxis.set_ticks([minprecip, minprecip + 0.5*(maxprecip-minprecip), maxprecip])
        ax2.yaxis.set_major_formatter(mpl.ticker.FormatStrFormatter('%.2f'))

    # lines emphasizing location of today and tomorrow
    ax1.plot([itoday - 1.5, itoday - 1.5], [mintemp, 0.9*maxtemp], color='black', linestyle='--', linewidth=3)
    ax1.plot([itoday + 1.5, itoday + 1.5], [mintemp, 0.9*maxtemp], color='black', linestyle='--', linewidth=3)
    ax1.plot([itoday + 4.5, itoday + 4.5], [mintemp, 0.9*maxtemp], color='black', linestyle='--', linewidth=3)
    ax1.plot([itoday + 7.5, itoday + 7.5], [mintemp, 0.9*maxtemp], color='black', linestyle='--', linewidth=3)

    # extra n/a for missing forecasts (wind also prints an n/a)
    for im in imissing:
        ax1.text(im, mintemp + 0.5*(maxtemp - mintemp), 'n/a', color=rain_color, fontsize=25)

    # freezing level line
    ax1.plot([-0.2, 7./8 * len(fake_date_range)], [utils.freezing_point, utils.freezing_point], color='blue', linestyle='--', linewidth=1)
    # ax1.plot([3./4 * len(fake_date_range), len(fake_date_range)], [utils.freezing_point, utils.freezing_point], color='blue', linestyle='--', linewidth=1)

    ax1.spines['top'].set_visible(False)
    ax1.get_xaxis().tick_bottom()

    fig.text(0.935, 0.63, 'rain (in.)', color=rain_color, fontsize=20, alpha=0.5)
    fig.text(0.935, 0.58, 'snow (ft.)', color=snow_color, fontsize=20, alpha=0.5)
    fig.text(0.004, 0.6, 'deg F', color='black', fontsize=20)
    fig.text(0.02, 0.32, 'hi', color=hi_color, fontsize=20)
    fig.text(0.02, 0.27, 'lo', color=lo_color, fontsize=20)
    plt.suptitle(location_title + '   (' + str(int(round(elevation, -2))) + ' ft)', fontsize=30)

    make_wind_plot(axwind, combined_forecasts, fake_date_range, total_width, total_height, height_ratios, wind_color)

    # ----------------------------------------------------------------------------------------
    plt.savefig(plotdir + '/' + filenamestr + '.svg')
    plt.close()
    # return plotfname.replace(htmldir + '/', '')

