#!/usr/bin/env python
# helps a bit: convert tmp.png -morphology erode:1 square:1 m.png

from PIL import Image  # install with pypi package 'pillow' (it's a PIL fork)
import os
import time
import csv
import sys
import glob
from subprocess import check_call, CalledProcessError
from lxml import etree
import urllib
import datetime
import calendar
import pytesseract  # have to do both: pip --user pytesseract and sudo apt-get install tesseract-ocr
import argparse
import colored_traceback.always
import traceback
from dateutil import tz
import tempfile
from collections import OrderedDict
import traceback
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

front_page_url = 'https://atmos.washington.edu/wrfrt/data/run_status.html'
wrfdir = os.path.dirname(os.path.realpath(__file__))
dummy_image_path = wrfdir + '/woot.png'
model_strings = ['WRF-GFS'] #, 'Extended WRF-GFS']

titles = {
    '3-hour-precip' : 'precip in previous 3 hours',
    'snow' : 'snowfall in previous 3 hours',
    'model-snow' : 'model snowfall in previous 3 hours',
    'snow-and-precip' : 'snowfall+precip in previous 3 hours',
    '24-hour-precip' : 'precip in previous 24 hours',
    'surface-temp' : 'surface temperature',
    '10m-wind-speed' : '10m wind speed',
    'integrated-cloud' : 'column-integrated cloud water'
}
# def get_short_name(name):
#     if 'snow' in name:
#         return 'snow'
#     else:
#         return name.replace('-', ' ')
# def short_name_list(names):  # kind of hackey: returns short name for each name in <names>, except skipping any that are already there (just weirdness to allow all three of the different snow variables to show up in the same column in the link table)
#     short_names = []
#     for name in names:
#         sname = get_short_name(name)
#         if sname not in short_names:
#             short_names.append(sname)
#     return short_names

# ----------------------------------------------------------------------------------------
expected_date_format = ('hours', 'tz', 'weekday', 'monthday', 'month', 'year')
# ----------------------------------------------------------------------------------------
def convert_dateinfo(dateinfo):
    for key in ('hours', 'monthday', 'year'):  # all the integers
        dateinfo[key] = dateinfo[key].replace('O', '0').replace('l', '1').replace('i', '1')
        dateinfo[key] = int(dateinfo[key])
    dateinfo['year'] += 2000
# ----------------------------------------------------------------------------------------
def get_imonth(dateinfo):
    if dateinfo['month'] not in calendar.month_abbr:
        dateinfo['month'] = dateinfo['month'].replace('n]', 'y').replace('V', 'y')
    return list(calendar.month_abbr).index(dateinfo['month'])

typical_hours_between_init_and_zero_fcast_hour = 4
side_indices = {'left' : 0, 'right' : 1, 'top' : 2, 'bottom' : 3}
base_margins = {  # (left, right, top, bottom)
    'full' : (0, 0, 0, 0),
    'init-time' : (500, 0, 0, 878),
    'entire-date-line' : (0, 0, 21, 855),
    'right-legend' : (850, 3, 100, 70)
}
specific_margins = {  # (left, right, top, bottom)
    'washington-plus' : {
        'date' : (630, 123, 21, 855),
        'full-date' : (630, 5, 21, 855),
        'howe-to-chehalis' : (250, 530, 110, 740),
        'western-wa-sw-bc' : (325, 430, 155, 500),
    },
    'pacific-northwest' : {
        'date' : (620, 110, 21, 855),
        'full-date' : (643, 5, 21, 855),
        'western-wa-sw-bc' : (200, 475, 180, 350),
    },
    'washington' : {
        'date' : (653, 123, 21, 855),
        'full-date' : (643, 5, 21, 855),
        'howe-to-chehalis' : (175, 475, 175, 650),
        'cascades' : (310, 415, 250, 300)
    },
    'western-washington' : {
        'date' : (630, 123, 21, 855),
        'full-date' : (630, 5, 21, 855),
        'cascades' : (550, 70, 120, 100)
    },
    '12km-domain' : {
        'date' : (630, 123, 21, 855),
        'full-date' : (630, 5, 21, 855),
        'wa-sw-bc' : (350, 200, 130, 350),
    },
}
# ----------------------------------------------------------------------------------------
def get_margins(maptype):
    margins = base_margins.copy()
    margins.update(specific_margins[maptype])
    return margins
    
paste_sizes = {  # final/total image sizes # (width, height) in pixels
    'washington-plus' : (280, 604), #(160, 330),
    'pacific-northwest' : (180, 325),
    'washington' : (175, 460),
    'western-washington' : (280, 650),
    '12km-domain' : (300, 400),
}
rescale_pixels = {
    'full-date' : (300, 40),
    'howe-to-chehalis' : (250, None),
    'western-wa-sw-bc' : (250, None),
}

paste_positions = {  # (x, y) coords of upper left corner
    'washington-plus' : {
        'full-date' : (0, 0),
        'howe-to-chehalis' : (0, 50),
        'western-wa-sw-bc' : (0, 160),
    },
    'pacific-northwest' : {
        'date' : (0, 0),
        'western-wa-sw-bc' : (0, 28),
    },
    'washington' : {
        'date' : (0, 0),
        'howe-to-chehalis' : (0, 28),
        'cascades' : (0, 107),
    },
    'western-washington' : {
        'full-date' : (0, 0),
        'cascades' : (0, 30),
    },
    '12km-domain' : {
        'date' : (0, 0),
        'wa-sw-bc' : (0, 30),
    },
}

base_url = 'http://www.atmos.washington.edu/wrfrt/data/timeindep'
base_outdir = 'images'
domain_codes = {
    '1.33km' : 'd4',
    '4km' : 'd3',
    '12km' : 'd2',
    '36km' : 'd1'
}
maptype_codes = {
    'washington-plus' : '',
    'pacific-northwest' : '',
    'washington' : 'wa_',
    'western-washington' : 'ww_',
    '12km-domain' : '',
}
# http://www.atmos.washington.edu/wrfrt/rt/load.cgi?latest+YYYYMMDDHH/images_d2/pcp3.00.0000.gif
variable_codes = {
    '3-hour-precip' : 'pcp3',
    'model-snow' : 'msnow3',
    'snow' : 'snow3',  # i don't know the difference between 'model snow' and 'snow', but i really wish i did [using snow for 4km, since it doesn't have 3hr model snow)
    'snow-and-precip' : 'rsnow3',
    '24-hour-precip' : 'pcp24',
    'surface-temp' : 'tsfc',
    '10m-wind-speed' : 'wssfc2',
    'integrated-cloud' : 'intcld'
}
exp_hour_values = {  # these all start at 6 because there never seems to be a 3, and 0 seems to be broken (or at least the precip ones always have zero precipe)
    '84-every-3' : list(range(6, 84+1, 3)),
    '72-every-3' : list(range(6, 72+1, 3)),
    '180-every-3' : list(range(6, 180+1, 3)),
    '180-every-12' : list(range(24, 180+1, 12)),
}
expected_hours = {
    '12km' : {
        '24-hour-precip' : exp_hour_values['180-every-12'],
        '3-hour-precip' : exp_hour_values['180-every-3'],
        'surface-temp' : exp_hour_values['180-every-12'],
        '10m-wind-speed' : exp_hour_values['180-every-12'],
        'integrated-cloud' : exp_hour_values['180-every-3'],
        'model-snow' : exp_hour_values['180-every-3'],
    },
    '4km' : {
        '3-hour-precip' : exp_hour_values['84-every-3'],
        'snow-and-precip' : exp_hour_values['84-every-3'],
        'surface-temp' : exp_hour_values['84-every-3'],
        '10m-wind-speed' : exp_hour_values['84-every-3'],
        'integrated-cloud' : exp_hour_values['84-every-3'],
        'snow' : exp_hour_values['84-every-3'],
    },
    '1.33km' : {
        '3-hour-precip' : exp_hour_values['72-every-3'],
        'model-snow' : exp_hour_values['72-every-3'],
        'snow-and-precip' : exp_hour_values['72-every-3'],
        'surface-temp' : exp_hour_values['72-every-3'],
        '10m-wind-speed' : exp_hour_values['72-every-3'],
        'integrated-cloud' : exp_hour_values['72-every-3'],
    }
}

final_image_params = {
    'margin' : 10,
    'columns' : 10
}

# grey: #656363
htmlheader = """<!DOCTYPE html>
<html>
<body style="background-color:black;">
"""
htmlfooter = """</body>
</html>
"""
ordered_domains = ['1.33km', '4km', '12km']  # way eaiser than sorting them afterward
header_links = [
    ['windguru', 'https://www.windguru.cz'],
    ['spotwx', 'https://spotwx.com/'],
    ['meteoblue', 'https://www.meteoblue.com/en/weather/forecast/multimodel/'],
]

# ----------------------------------------------------------------------------------------
def get_subimage(img, rname, margins):
    tmpco = {side : margins[rname][iside] for side, iside in side_indices.items()}
    width, height = img.size
    bbox = (tmpco['left'], tmpco['top'], width - tmpco['right'], height - tmpco['bottom'])
    subimg = img.crop(bbox)
    if rname in rescale_pixels:  # doesn't work for shit (well, it's too few pixels so it's hard to read the date)
        scale_pair = list(rescale_pixels[rname])
        assert scale_pair[0] is not None  # easy to implement, but I don't need it right now
        if scale_pair[1] is None:
            scale_pair[1] = int(subimg.size[1] * float(scale_pair[0]) / subimg.size[0])
            # assert float(scale_pair[0]) / subimg.size[0] == float(scale_pair[1]) / subimg.size[1]
        subimg = subimg.resize(scale_pair) #, resample=Image.LANCZOS)
    return subimg

# ----------------------------------------------------------------------------------------
def get_url(domain, maptype, variable, hour):
    return base_url + '/images_' + domain_codes[domain] + '/' + maptype_codes[maptype] + variable_codes[variable] + '.' + ('%02d' % hour) + '.0000.gif'

# ----------------------------------------------------------------------------------------
def get_legend_fname(maptype, variable):
    if 'precip' in variable:  # this now also picks up 'snow-and-precip'
        variable_category = 'precip'
    elif 'snow' in variable:
        variable_category = 'snow'
    elif 'temp' in variable:
        variable_category = 'temp'
    elif 'wind' in variable:
        variable_category = 'wind'
    elif 'cloud' in variable:
        variable_category = 'cloud'
    else:
        assert False

    legend_dir = 'legends/' + maptype  # *relative* path
    legendfname = variable_category + '.svg'
    if not os.path.exists(args.outdir + '/' + legend_dir):
        os.makedirs(args.outdir + '/' + legend_dir)
    check_call(['cp', wrfdir + '/' + legend_dir + '/' + legendfname, args.outdir + '/' + legend_dir + '/' + legendfname])

    return legend_dir + '/' + legendfname

# ----------------------------------------------------------------------------------------
def get_fname(domain, maptype, variable, hour, processed=False):
    # NOTE this is the *relative* path, used for links
    outpath = base_outdir
    suffix = 'gif'
    if processed:
        outpath += '/processed'
        suffix = 'png'
    outpath += '/' + domain + '/' + maptype + '/' + variable + '/' + str(hour) + '.' + suffix
    return outpath

# ----------------------------------------------------------------------------------------
def download_image(domain, maptype, variable, hour):
    outfname = args.outdir + '/' + get_fname(domain, maptype, variable, hour)
    if args.no_download:
        print '    --no-download: doing nothing'
        return
    if not os.path.exists(os.path.dirname(outfname)):
        os.makedirs(os.path.dirname(outfname))
    url = get_url(domain, maptype, variable, hour)
    try:
        urllib.urlretrieve(url, outfname)
        # check_call(['wget', '-O', outfname, url])
    except CalledProcessError:
        print '  failed retrieving %s' % url
        os.remove(outfname)

# ----------------------------------------------------------------------------------------
def download_all_images(domain, maptype, variable):
    for hour in expected_hours[domain][variable]:
        download_image(domain, maptype, variable, hour)

# ----------------------------------------------------------------------------------------
def join_image_pieces(subimages, maptype):
    # joined_image = Image.new("RGB", (subimages['cascades'].size[0], subimages['cascades'].size[1] + subimages['date'].size[1]))
    joined_image = Image.new("RGB", paste_sizes[maptype])  # (width, height) in pixels
    for name, ppos in paste_positions[maptype].items():
        joined_image.paste(subimages[name], ppos)  # second arg is 2-tuple giving upper left corner (can also be a 4-tuple giving the (left, upper, right, lower) pixel coordinate (in latter case, size of pasted image must match)
    return joined_image

# # ----------------------------------------------------------------------------------------
# def run_tesseract(img):
#     return_str = pytesseract.image_to_string(img)
#     # tmptiff = '/tmp/tmp-date-image.tiff'
#     # tmptxt = '/tmp/tmp-date-image'
#     # img.save(tmptiff)
#     # check_call(['tesseract', tmptiff, tmptxt])
#     # with open(tmptxt + '.txt') as txtfile:
#     #     return_str = txtfile.read()
#     # os.remove(tmptiff)
#     # os.remove(tmptxt + '.txt')
#     print return_str
#     return return_str

# ----------------------------------------------------------------------------------------
def get_single_date(img, fname):
    try:
        datestr = str(pytesseract.image_to_string(img))
        # img.save(os.getenv('www') + '/tmp/tmp.png')
        # sys.exit()
    except:
        elines = traceback.format_exception(*sys.exc_info())
        print ''.join(elines)
        print '  failed running tesseract'
        return None
    else:
        try:
            # old version for full non-init date line:
            # datelist = datestr[datestr.find('(') + 1 : datestr.find(')')].replace('\'', '').split()
            # new version for init time:
            datelist = datestr.translate(None, '_\'\"();:{}').split()
            if 'UTC' not in datelist:
                print '  \'UTC\' not found in \'%s\'' % datestr
                return None
            utc_str_index = datelist.index('UTC')  # index of the string \'UTC\'
            datelist = datelist[utc_str_index - 1 : ]  # i.e. trim off the 'Init:'
            dateinfo = {}
            for ifmt in range(len(expected_date_format)):
                dateinfo[expected_date_format[ifmt]] = datelist[ifmt]
            convert_dateinfo(dateinfo)
            imonth = get_imonth(dateinfo)
            utc_init_time = datetime.datetime(dateinfo['year'], imonth, dateinfo['monthday'], dateinfo['hours'])
            utc_init_time = utc_init_time.replace(tzinfo=tz.gettz('UTC'))  # tell the datetime object that it's in UTC time zone since datetime objects are 'naive' by default
            pdt_init_time = utc_init_time.astimezone(tz.gettz('PDT'))
        except Exception, e:
            print '  couldn\'t convert tesseract output string \'%s\' from %s' % (datestr, fname)
            print e
            return None
    return pdt_init_time

# ----------------------------------------------------------------------------------------
def set_dates(imgfo):
    # first find one date that we can get
    init_time = None
    for iimg in range(len(imgfo)):
        if init_time is None:
            init_time = get_single_date(imgfo[iimg]['subimages']['init-time'], imgfo[iimg]['fname'])
            break
    if init_time is None:  # couldn't get it from any of the images
        init_time = datetime.datetime.now() - datetime.timedelta(hours=typical_hours_between_init_and_zero_fcast_hour)

    # then set everybody's info accordingly
    for iimg in range(len(imgfo)):
        imgfo[iimg]['datetime'] = init_time + datetime.timedelta(hours=(imgfo[iimg]['fcast-hour']))  #  - known_fcast_hour))
        # print '  %2d  %s' % (imgfo[iimg]['fcast-hour'], imgfo[iimg]['datetime'].strftime('%a %H:%M'))

# ----------------------------------------------------------------------------------------
def dummy_image():
    return Image.new("RGB", (10, 10))

# ----------------------------------------------------------------------------------------
def get_fcast_image_info(domain, maptype, variable, hour):
    fname = args.outdir + '/' + get_fname(domain, maptype, variable, hour)
    if os.path.exists(fname):
        pass
        # print '  already exists: %s' % fname
    else:
        print '  downloading %s' % fname
        download_image(domain, maptype, variable, hour)
    margins = get_margins(maptype)
    if os.path.exists(fname):
        try:
            img = Image.open(fname)  # model snow is giving me invalid gifs... then again it's late july, so maybe that's on purpose
        except IOError as e:
            print '    %s' % e
            img = Image.open(dummy_image_path)
        subimages = {sname : get_subimage(img, sname, margins) for sname in margins}
        final_image = join_image_pieces(subimages, maptype)
    else:
        final_image = dummy_image()
        subimages = {sname : dummy_image() for sname in margins}

    # # print subimage sizes
    # for si in subimages:
    #     print '%40s %3d %3d' % (si, subimages[si].size[0], subimages[si].size[1])
    # sys.exit()

    # # write individual subimage
    # if hour == 42:
    #     subimages['howe-to-chehalis'].save('tmp.png')
    #     sys.exit()

    processed_fname = args.outdir + '/' + get_fname(domain, maptype, variable, hour, processed=True)
    if not os.path.exists(os.path.dirname(processed_fname)):
        os.makedirs(os.path.dirname(processed_fname))
    final_image.save(processed_fname)

    return {'fcast-hour' : hour, 'fname' : processed_fname, 'subimages' : subimages}

# ----------------------------------------------------------------------------------------
def join_fcasts(domain, maptype, variable):
    imgfo = []
    for hour in expected_hours[domain][variable]:
        imgfo.append(get_fcast_image_info(domain, maptype, variable, hour))  # if it fails, for whatever reason, it'll put in a dummy image
    set_dates(imgfo)

    return imgfo

# ----------------------------------------------------------------------------------------
def get_htmlfname(domain, variable):
    # NOTE *relative* path
    return domain + '_' + variable + '.html'

# ----------------------------------------------------------------------------------------
def reverse_htmlfname(fname):
    return os.path.basename(fname).replace('.html', '').split('_')

# ----------------------------------------------------------------------------------------
def link_str(name, url):
    return '<a  href="%s"><font color=#4b92e7 size=3>%s</font></a>' % (url, name)

# ----------------------------------------------------------------------------------------
def get_link_lines(all_fnames):
    fnames = sorted(all_fnames)
    lines = []

    # first add external links
    lines += ['<font color=white size=3>%s</font>' % 'other models: ']
    for name, url in header_links:
        # lines.append('<a href="' + url + '"><font size=3>' + name + '</font></a>')
        lines.append(link_str(name, url))
    lines.append('<br>\n')

    lines += ['<font color=white size=3>%s</font>' % 'wrf source: ']
    # lines += ['<a  href="%s"><font color=#4b92e7 size=3>%s</font></a>' % ('https://atmos.washington.edu/wrfrt/gfsinit.html', 'atmos.washington.edu')]
    lines += [link_str('atmos.washington.edu', 'https://atmos.washington.edu/wrfrt/gfsinit.html')]
    lines.append('<br>\n')

    lines += ['<font color=white size=3>%s</font>' % 'seattle monthly averages: ']
    lines += [link_str('rainfall', 'images/average-monthly-rainfall.png')]
    lines += [link_str('chance of precip', 'daily-precip-chance.png')]
    lines.append('<br>\n')
    lines.append('<br>\n')

    # then add links to each set of uw wrf plots that we made
# ----------------------------------------------------------------------------------------
# TODO clean this up! looks like I left it in a sorry state but can't be bothered now since I want to commit for something else
    info = OrderedDict()
    for fname in fnames:
        domain, var = reverse_htmlfname(fname)
        if domain not in info:
            info[domain] = OrderedDict()
        if var not in info[domain]:
            info[domain][var] = fname

    all_vars = sorted(set([v for d in info for v in info[d]]))
    # all_domains = ['%fkm' % dstr for dstr in sorted([float(d.rstrip('km')) for d in info])]  # sort the domains by increasing domain size
    lines += ['<table style="width:75%">']
    lines += ['<tr>']
    lines += ['<th></th>']  # blank one for domain names
    lines += ['<th><font color=white size=3>%s</font></th>' % v.replace('-', ' ') for v in all_vars]
    # lines += ['<th><font color=white size=3>%s</font></th>' % sv for sv in short_name_list(all_vars)]
    lines += ['</tr>']
     # {text-align:center}
    for domain in [d for d in ordered_domains if d in info]:
        lines += ['<tr>']
        lines += ['<td><font color=white size=3>%s</font></td>' % domain]
        for var in all_vars:
            if var in info[domain]:
                # lines += ['<td><a href="%s"><font color=#4b92e7 size=3>%s</font></a></td>' % (info[domain][var], domain)]
                lines += ['<td>%s</a></td>' % link_str(domain, info[domain][var])]
            else:
                lines += ['<td></td>']
        lines += ['</tr>']
    lines += ['</table>']
# ----------------------------------------------------------------------------------------
    # linkstr = '<a href="' + fname + '"><font size=3>' + variable.replace('-', ' ') + '</font></a>'
    # all_domains, all_vars = [sorted(list(set(thislist))) for thislist in zip(*[reverse_htmlfname(fname) for fname in fnames])]

    # last_domain = None
    # for fname in fnames:
    #     domain, variable = reverse_htmlfname(fname)
    #     linkstr = '<a href="' + fname + '"><font size=3>' + variable.replace('-', ' ') + '</font></a>'
    #     if last_domain is None or domain != last_domain:
    #         linkstr = '<font color=white>' + domain + ': </font>' + linkstr
    #     if last_domain is not None and domain != last_domain:
    #         linkstr = '<br>\n' + linkstr
    #     lines.append(linkstr)
    #     last_domain = domain

    return lines

# ----------------------------------------------------------------------------------------
def write_index_html(fname, all_fnames):
    with open(fname, 'w') as htmlfile:
        htmlfile.write(htmlheader)
        for line in get_link_lines(all_fnames):
            htmlfile.write(line + '\n')
        htmlfile.write(htmlfooter)

# ----------------------------------------------------------------------------------------
def add_linkstrs(fname, all_fnames):
    with open(args.outdir + '/' + fname) as htmlfile:
        lines = htmlfile.readlines()
    with open(args.outdir + '/' + fname, 'w') as htmlfile:
        for line in lines:
            if '<body' in line:  # look for <htmlheader>
                # htmlfile.write('<center>\n')
                for link in get_link_lines(all_fnames):
                    htmlfile.write(link + '\n')
                # htmlfile.write('</center>\n')
                htmlfile.write('<br>\n<br>\n')
            htmlfile.write(line)

# ----------------------------------------------------------------------------------------
def write_html(domain, maptype, variable):
    imgfo = join_fcasts(domain, maptype, variable)
    htmlfname = args.outdir + '/' + get_htmlfname(domain, variable)
    # if not os.path.exists(os.path.dirname(htmlfname)):
    #     os.makedirs(os.path.dirname(htmlfname))
    with open(htmlfname, 'w') as htmlfile:
        htmlfile.write(htmlheader)
        htmlfile.write('<center><font color=white size=2>first plot: %s</font></center>\n' % imgfo[0]['datetime'].strftime('%a %B %d %Y %H:%M PDT'))
        htmlfile.write('<center><font color=red size=4>%s</font></center>\n' % titles[variable])
        htmlfile.write('<br><br>\n')
        last_weekday = None
        for ifn in range(len(imgfo)):
            if variable == '24-hour-precip' and imgfo[ifn]['datetime'].hour == 5:
                continue
            if last_weekday is not None and imgfo[ifn]['datetime'].weekday() != last_weekday:
                htmlfile.write('<br>\n')
            last_weekday = imgfo[ifn]['datetime'].weekday()
            htmlfile.write('<a href="' + get_fname(domain, maptype, variable, imgfo[ifn]['fcast-hour'], processed=False) + '"> <img alt="foop", src="' + get_fname(domain, maptype, variable, imgfo[ifn]['fcast-hour'], processed=True) + '", width="150"> </a>\n')
        htmlfile.write('<br>\n')
        htmlfile.write('<center><a href="' + get_legend_fname(maptype, variable) + '"><img src="' + get_legend_fname(maptype, variable) + '", width="' + ('500' if 'wind' in variable else '350') + '"></a></center>\n')
        htmlfile.write(htmlfooter)

# ----------------------------------------------------------------------------------------
def get_run_status_times(td):
    if 'STATUS' not in td.text:
        raise Exception('unexpected status line \'%s\'' % td.text)
    txtlist = td.text.split()

    if txtlist[:2] != ['STATUS', 'of']:
        raise Exception('unexpected status line %s' % txtlist[:2])
    run_time_str = txtlist[2]
    if len(run_time_str) != 10:
        raise Exception('couldn\'t convert run time %s' % run_time_str)
    year = int(run_time_str[:4])  # NOTE used below for status time
    month = int(run_time_str[4:6])
    day = int(run_time_str[6:8])
    hour = int(run_time_str[8:10])
    run_time = datetime.datetime(year=year, month=month, day=day, hour=hour)  # initialization time, I think (probably utc)

    if txtlist[3:7] != ['UW', 'runs', 'as', 'of']:
        raise Exception('unexpected status line %s' % txtlist[3:7])

    if len(txtlist) != 12:
        raise Exception('unexpected status line %s' % txtlist[7:])
    status_time_list = txtlist[7:12]
    if len(status_time_list) != 5:
        raise Exception('unexpected status time \'%s\'' % status_time_list)
    hour, minute = [int(val) for val in status_time_list[0].split(':')]
    ampm = status_time_list[1]
    if ampm not in  ['am', 'pm']:
        raise Exception('unexpected ampm \'%s\'' % ampm)
    if hour == 12:
        if ampm == 'am':  # not sure if they call 30min after midnight 12:30 or 00:30... but this should handle either
            hour -= 12
    else:
        if ampm == 'pm':
            hour += 12
    tzstr = status_time_list[2]
    if tzstr not in ['PDT', 'PST']:
        raise Exception('unexpected time zone \'%s\'' % tzstr)
    month_str = status_time_list[3]
    month = int(list(calendar.month_abbr).index(month_str))
    day = int(status_time_list[4])
    status_time = datetime.datetime(year=year, month=month, day=day, hour=hour)  # time that it wrote this status file NOTE using year from run time above

    return run_time, status_time

# ----------------------------------------------------------------------------------------
def get_status(modeltype, cachefname=None, debug=False):
    # note: you really don't want to download images while the fcasts are running, since they go through their file system gradually replacing files as they run (i.e. you'll download an inconsistent series of images)
    parser = etree.HTMLParser()

    # cachefname = '/home/dralph/weatherscraper/wrfparser/_cache/WRF-GFS-2017-09-09_11:33:03.973294-status.html'
    # tree = etree.parse(cachefname, parser)
    with tempfile.NamedTemporaryFile() as tmpfile:
        if debug:
            print '    retrieving %s' % front_page_url
        try:
            urllib.urlretrieve(front_page_url, tmpfile.name)
        except IOError as e:
            print '    %s' % e
            return 'unknown'
        tree = etree.parse(tmpfile, parser)
    if cachefname is not None:  # write html to a file in case we want it later
        if debug:
            print '    writing html to %s' % cachefname
        tmpstr = etree.tostring(tree.getroot(), pretty_print=True, method='html')
        with open(cachefname, 'w') as tmpfile:
            tmpfile.write(tmpstr)

    tdlist = list(tree.findall('.//td'))
# ----------------------------------------------------------------------------------------
# they changed the format, so hacking this on
    assert len(tdlist) == 2
    st_text = tdlist[1].text
    if st_text in ['complete', 'running']:
        return st_text
    elif 'to hour' in st_text or '1 1/3km to hr' in st_text:
        print '  status: %s' % st_text
        return 'running'
    print '  unknown status: \'%s\'' % st_text
    return 'unknown'
# ----------------------------------------------------------------------------------------
    run_time, status_time = get_run_status_times(tdlist[1])
    if debug:
        print '       run time: %s ' % run_time
        print '    status time: %s ' % status_time
    if len(tdlist) % 2 != 1:
        raise Exception('bad tdlist length %d' % len(tdlist))
    tdpairs = [(tdlist[i], tdlist[i + 1]) for i in range(1, len(tdlist), 2)]
    for nametd, statustd in tdpairs:
        hlink = nametd.find('.//a')
        if hlink.text == modeltype:
            print '    %s: %s' % (hlink.text, statustd.text)
            if statustd.text == 'complete':
                return 'complete'
            else:
                return 'running'

    return 'unknown'

# ----------------------------------------------------------------------------------------
def check_all_models_complete(debug=False):
    if args.test:
        return True

    cachedir = wrfdir + '/_cache'
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)

    statuses = []
    for mstr in model_strings:
        status = get_status(mstr, debug=debug)
        if debug:
            print '  %s: %s' % (mstr, status)

        if status == 'running':
            return False
        elif status == 'unknown':
            cachefname = cachedir + '/%s-%s-status.html' % (mstr, datetime.datetime.now().__str__().replace(' ', '_'))
            print '  unknown status for %s, writing html to %s' % (mstr, cachefname)
            status = get_status(mstr, cachefname=cachefname, debug=debug)
            return False

        statuses.append(status)

    if statuses.count('complete') != len(statuses):
        print 'wtf? fell through, but not all statuses are \'complete\': %s' % statuses
        return False

    return True

# ----------------------------------------------------------------------------------------
def run():
    stuff_to_run = []
    with open(args.config_fname) as cfgfile:
        reader = csv.DictReader(row for row in cfgfile if not row.startswith('#'))
        for line in reader:
            stuff_to_run.append(line)

    for line in stuff_to_run:
        print line['domain'], line['variable']
        if not args.no_download:  # if the images aren't there I think it will still try to download them one by one
            download_all_images(line['domain'], line['maptype'], line['variable'])
        write_html(line['domain'], line['maptype'], line['variable'])

    htmlfnames = [get_htmlfname(line['domain'], line['variable']) for line in stuff_to_run]
    for line in stuff_to_run:
        add_linkstrs(get_htmlfname(line['domain'], line['variable']), htmlfnames)

    write_index_html(args.outdir + '/index.html', htmlfnames)

# ----------------------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--outdir', required=True)
parser.add_argument('--config-fname', default=wrfdir + '/config.csv')
parser.add_argument('--test', action='store_true')
parser.add_argument('--no-sleep', action='store_true')
parser.add_argument('--no-download', action='store_true')
parser.add_argument('--no-push', action='store_true')
args = parser.parse_args()

running_sleep_time = 1800  # 1800s = 30m
just_finished_sleep_time = 21600  # 21600s is 6h
if args.test:
    args.no_sleep = True
    args.no_download = True
    args.no_push = True

while True:
    all_complete = check_all_models_complete(debug=True)
    while not args.no_sleep and not all_complete:
        print '  %s: forecasts are running, sleep for %d min' % (datetime.datetime.now().strftime('%a %B %d %H:%M'), int(running_sleep_time / 60.))
        time.sleep(running_sleep_time)
        all_complete = check_all_models_complete(debug=True)

    try:
        run()
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print ''.join(lines)
        print '      failed to run (see above), continuing'
        if args.test or args.no_sleep:
            break
        else:
            continue

    if not args.no_push:
        check_call([wrfdir + '/upload.sh', args.outdir.replace('/wrfparser', '')])
        if not args.no_sleep:
            time.sleep(just_finished_sleep_time)

    if args.test or args.no_sleep:
        break
