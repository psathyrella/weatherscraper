import os
import sys
import math
import numpy
from datetime import datetime

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

import utils

# ----------------------------------------------------------------------------------------
def make_noaa_history_plot(args, location_name, htmldir, history):
    """ NOTE this is *extremely* similar to the function below, I'm just keeping it around for a bit so I can still make the old html """
    if not os.path.exists(htmldir + '/history'):
        os.makedirs(htmldir + '/history')
    if history is None or args.no_history:  # will also fail if we only have one day's worth of history
        return None

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
    # plt.locator_params(nbins=nxbins, axis='x')
    # plt.locator_params(nbins=nybins, axis='y')

    ax2 = ax1.twinx()
    liquid_color = '#1947D1'
    snow_color = 'grey'

    # figliquid = ax2.plot(history['days'], history['liquid'], color=liquid_color, linewidth=3)
    # figliquid = ax2.plot(history['days'], history['snow'], color=snow_color, linewidth=3)

    liquid_hist, liquid_weights = [], []
    snow_hist, snow_weights = [], []
    n_big_number = 1e5
    for iday in range(len(history['days'])):
        day = history['days'][iday]
        if history['liquid'][iday] is not None:
            for il in range(int(n_big_number*history['liquid'][iday]) + 1):  # NOTE this gives you 1./n_big_number instead of zero
                liquid_hist.append(iday)
                liquid_weights.append(1./n_big_number)
        if history['snow'][iday] is not None:
            for il in range(int(n_big_number*history['snow'][iday]) + 1):  # NOTE this gives you 1./n_big_number instead of zero
                snow_hist.append(iday)
                snow_weights.append(1./n_big_number)

    # date_range = range(history['days'][0], history['days'][0] + len(history['days']))
    fake_date_range = range(len(history['days']))

    ax2.hist(liquid_hist, bins=len(history['days']), range=(fake_date_range[0]-.6, fake_date_range[-1]+.4), weights=liquid_weights, rwidth=.5, color=liquid_color, alpha=0.5)
    ax2.hist(snow_hist, bins=len(history['days']), range=(fake_date_range[0]-.4, fake_date_range[-1]+.6), weights=snow_weights, rwidth=.5, color=snow_color, alpha=0.5)

    fighi = ax1.plot(fake_date_range, history['hi'], color=hi_color, linewidth=5)
    figlo = ax1.plot(fake_date_range, history['lo'], color=lo_color, linewidth=5)

    # plt.locator_params(nbins=nxbins, axis='x')
    # plt.locator_params(nbins=nybins, axis='y')
    plt.gcf().subplots_adjust(bottom=0.1, left=0.11, right=0.87, top=0.85)
    plt.xlim(fake_date_range[0] - 0.25, fake_date_range[-1] + 0.25)
    xticklabels = ax2.get_xticks().tolist()
    assert len(xticklabels) == len(history['days']) + 2
    for itick in range(1, len(xticklabels)-1):  # first and last are overflow bins or something
        xticklabels[itick] = history['days'][itick-1]
    ax2.set_xticklabels(xticklabels)

    mintemp = min(t for t in history['lo'] if t is not None)
    maxtemp = max(t for t in history['hi'] if t is not None)
    minprecip = min(p for p in history['liquid'] + history['snow'] if p is not None)  # snow's already been converted to feet
    maxprecip = max(p for p in history['liquid'] + history['snow'] if p is not None)

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

    ax1.spines['top'].set_visible(False)
    ax1.get_xaxis().tick_bottom()

    fig.text(0.88, 0.7, 'in.', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.93, 0.7, 'ft.', color=snow_color, fontsize=20, alpha=0.5)
    fig.text(0.003, 0.7, 'deg F', color='black', fontsize=20)
    fig.text(0.02, 0.35, 'hi', color=hi_color, fontsize=20)
    fig.text(0.02, 0.3, 'lo', color=lo_color, fontsize=20)
    fig.text(0.87, 0.35, 'precip', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.88, 0.3, 'snow', color=snow_color, fontsize=20, alpha=0.5)
    plt.suptitle(location_name, fontsize=20)

    plotfname = htmldir + '/history/' + location_name + '.png'
    plt.savefig(plotfname)
    return plotfname.replace(htmldir + '/', '')

# ----------------------------------------------------------------------------------------
def make_combined_noaa_plot(args, location_name, htmldir, history, todays_forecast, forecasts):
    print 'starting plot'
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

    fig, ax1 = plt.subplots()
    fig.set_size_inches(25, 5)
    lo_color = '#99B2FF'
    hi_color = 'red'
    # plt.locator_params(nbins=nxbins, axis='x')
    # plt.locator_params(nbins=nybins, axis='y')
    combined_forecasts = {}
    for var in history:
        if var == 'days':
            continue
        combined_forecasts[var] = history[var] + todays_forecast[var] + forecasts[var]

    ax2 = ax1.twinx()
    liquid_color = '#1947D1'
    snow_color = 'grey'

    n_days = len(combined_forecasts['dates'])

    liquid_hist, liquid_weights = [], []
    snow_hist, snow_weights = [], []
    n_big_number = 1e2
    for iday in range(n_days):
        # day = combined_forecasts['days'][iday]
        if combined_forecasts['liquid'][iday] is not None:
            for il in range(int(n_big_number*combined_forecasts['liquid'][iday]) + 1):  # NOTE this gives you 1./n_big_number instead of zero
                liquid_hist.append(iday)
                liquid_weights.append(1./n_big_number)
        if combined_forecasts['snow'][iday] is not None:
            for il in range(int(n_big_number*combined_forecasts['snow'][iday]) + 1):  # NOTE this gives you 1./n_big_number instead of zero
                snow_hist.append(iday)
                snow_weights.append(1./n_big_number)

    # date_range = range(combined_forecasts['days'][0], combined_forecasts['days'][0] + n_days)
    fake_date_range = range(n_days)

    ax2.hist(liquid_hist, bins=n_days, range=(fake_date_range[0]-.6, fake_date_range[-1]+.4), weights=liquid_weights, rwidth=.5, color=liquid_color, alpha=0.5)
    ax2.hist(snow_hist, bins=n_days, range=(fake_date_range[0]-.4, fake_date_range[-1]+.6), weights=snow_weights, rwidth=.5, color=snow_color, alpha=0.5)

    fighi = ax1.plot(fake_date_range, combined_forecasts['hi'], color=hi_color, linewidth=5)
    figlo = ax1.plot(fake_date_range, combined_forecasts['lo'], color=lo_color, linewidth=5)

    # # plt.locator_params(nbins=nxbins, axis='x')
    # # plt.locator_params(nbins=nybins, axis='y')
    # plt.gcf().subplots_adjust(bottom=0.1, left=0.11, right=0.87, top=0.85)
    # plt.xlim(fake_date_range[0] - 0.25, fake_date_range[-1] + 0.25)
    # xticklabels = ax2.get_xticks().tolist()
    # assert len(xticklabels) == n_days + 2
    # for itick in range(1, len(xticklabels)-1):  # first and last are overflow bins or something
    #     xticklabels[itick] = combined_forecasts['dates'][itick-1].day
    # ax2.set_xticklabels(xticklabels)

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

    ax1.spines['top'].set_visible(False)
    ax1.get_xaxis().tick_bottom()

    fig.text(0.88, 0.7, 'in.', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.93, 0.7, 'ft.', color=snow_color, fontsize=20, alpha=0.5)
    fig.text(0.003, 0.7, 'deg F', color='black', fontsize=20)
    fig.text(0.02, 0.35, 'hi', color=hi_color, fontsize=20)
    fig.text(0.02, 0.3, 'lo', color=lo_color, fontsize=20)
    fig.text(0.87, 0.35, 'precip', color=liquid_color, fontsize=20, alpha=0.5)
    fig.text(0.88, 0.3, 'snow', color=snow_color, fontsize=20, alpha=0.5)
    plt.suptitle(location_name, fontsize=20)

    plotfname = htmldir + '/noaa/' + location_name + '.png'
    plt.savefig(plotfname)
    print 'finished plotting'
    return plotfname.replace(htmldir + '/', '')

# ----------------------------------------------------------------------------------------
def make_hists(forecasts, varname):
    hist, weights = [], []
    n_big_number = 1e2
    for ifc in range(len(forecasts)):
        fcast = forecasts[ifc]
        for il in range(int(n_big_number*float(fcast[varname])) + 1):  # NOTE this gives you 1./n_big_number instead of zero
            hist.append(ifc)
            weights.append(1./n_big_number)

    return hist, weights

# ----------------------------------------------------------------------------------------
def make_mtfcast_plot(args, location_name, location_title, elevation, plotdir, forecasts, history, daily_forecasts):
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

    from matplotlib import gridspec
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

    todaycast = forecasts[:3]
    tomorrowcast = forecasts[3:6]

    combined_forecasts = history + todaycast + tomorrowcast + daily_forecasts[2:]

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
    now = datetime.now()
    itoday = None
    for ifc in fake_date_range:
        fc = combined_forecasts[ifc]
        print '%4d  %5s    %8.2f   %8.1f' % (ifc, fc['date'].day, fc['snow'], fc['wind-speed'])
        xticks.append(ifc)
        if ifc < len(history):
            if ifc == int(len(history) / 2) - 1:  # near the middle of the history
                label = 'last %d days' % len(history)
            else:
                label = ''
        elif fc['date'].year == now.year and fc['date'].month == now.month and fc['date'].day == now.day:  # today
            if fc['time-of-day'] == 'AM':
                label = ''
            elif fc['time-of-day'] == 'PM':
                itoday = ifc
                label = 'today'
            elif fc['time-of-day'] == 'night':
                label = ''
        elif fc['date'].year == now.year and fc['date'].month == now.month and fc['date'].day == now.day + 1:  # tomorrow
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
    minprecip = min(p for p in [fc['rain'] + fc['snow'] for fc in combined_forecasts])  # snow's already been converted to feet
    maxprecip = max(p for p in [fc['rain'] + fc['snow'] for fc in combined_forecasts])

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

    ax1.spines['top'].set_visible(False)
    ax1.get_xaxis().tick_bottom()

    fig.text(0.935, 0.63, 'rain (in.)', color=rain_color, fontsize=20, alpha=0.5)
    fig.text(0.935, 0.58, 'snow (ft.)', color=snow_color, fontsize=20, alpha=0.5)
    fig.text(0.004, 0.6, 'deg F', color='black', fontsize=20)
    fig.text(0.02, 0.32, 'hi', color=hi_color, fontsize=20)
    fig.text(0.02, 0.27, 'lo', color=lo_color, fontsize=20)
    plt.suptitle(location_title + '   (' + str(int(round(elevation, -2))) + ' ft)', fontsize=20)

    # ----------------------------------------------------------------------------------------
    # wind
    max_wind = 60  # NOTE this doesn't saturate when you get this high, it's just that the arrow starts overflowing its allotted space
    # ax3 = ax1.twinx()
    # figwind = ax3.plot(fake_date_range, [min(fc['wind-speed'], max_wind) for fc in combined_forecasts], color=wind_color, linewidth=5, linestyle='-')
    # ax3.set_axis_off()
    # fig.text(0.01, 0.05, '0', color=wind_color, fontsize=30)
    # fig.text(0.01, 0.8, 'mph', color=wind_color, fontsize=30)

    axwind.set_xlim(0., 1.)
    axwind.set_ylim(-0.5, 0.5)
    xwidth = 1. / len(combined_forecasts)  # distance between forecasts
    for ifc in fake_date_range:
        fc = combined_forecasts[ifc]
        xpos = 0.5 * xwidth + float(ifc) / len(combined_forecasts)  # center of this forecast
        arrow_length = 0.9 * xwidth * fc['wind-speed'] / max_wind
        # slope = float(ifc) / len(combined_forecasts)
        # theta = math.atan(slope)
        theta = fc['wind-direction']  #2 * math.pi * float(ifc) / len(combined_forecasts)
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
    plt.savefig(plotdir + '/' + location_name + '-' + str(elevation) + '.png')
    # return plotfname.replace(htmldir + '/', '')

