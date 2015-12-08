import os
import sys
import math
import numpy
import datetime

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt

import utils

weekdays = ('Mon', 'Tues', 'Wed', 'Thurs', 'Fri', 'Sat', 'Sun')

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
    n_big_number = 1e2
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
    plt.close()
    return plotfname.replace(htmldir + '/', '')

