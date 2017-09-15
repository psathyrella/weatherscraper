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
from dateutil import tz
import tempfile

front_page_url = 'https://atmos.washington.edu/wrfrt/data/run_status.html'
model_strings = ['WRF-GFS'] #, 'Extended WRF-GFS']

titles = {
    '3-hour-precip' : 'precip in previous 3 hours',
    '24-hour-precip' : 'precip in previous 24 hours',
    'surface-temp' : 'surface temperature',
    '10m-wind-speed' : '10m wind speed',
    'integrated-cloud' : 'column-integrated cloud water'
}

expected_date_format = ('hours', 'tz', 'weekday', 'monthday', 'month', 'year')
def convert_dateinfo(dateinfo):
    for key in ('hours', 'monthday', 'year'):  # all the integers
        dateinfo[key] = dateinfo[key].replace('O', '0').replace('l', '1')
        dateinfo[key] = int(dateinfo[key])
    dateinfo['year'] += 2000

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
        'date' : (653, 123, 21, 855),
        'full-date' : (643, 5, 21, 855),
        'western-wa-sw-bc' : (275, 450, 220, 420),
    },
    'washington' : {
        'date' : (653, 123, 21, 855),
        'full-date' : (643, 5, 21, 855),
        'howe-to-chehalis' : (175, 550, 175, 650),
        'cascades' : (310, 415, 250, 300)
    },
    'western-washington' : {
        'date' : (630, 123, 21, 855),
        'full-date' : (630, 5, 21, 855),
        'cascades' : (550, 70, 120, 200)
    },
    '12km-domain' : {
        'date' : (630, 123, 21, 855),
        'full-date' : (630, 5, 21, 855),
        'wa-sw-bc' : (350, 200, 130, 450),
    },
}
# ----------------------------------------------------------------------------------------
def get_margins(maptype):
    margins = base_margins.copy()
    margins.update(specific_margins[maptype])
    return margins
    
paste_sizes = {  # final/total image sizes
    'washington-plus' : (160, 330),
    'pacific-northwest' : (180, 260),
    'washington' : (175, 460),
    'western-washington' : (280, 604),
    '12km-domain' : (300, 350),
}
rescale_pixels = {
    'full-date' : (150, 20),
}

paste_positions = {  # (x, y) coords of upper left corner
    'washington-plus' : {
        'full-date' : (0, 0),
        'howe-to-chehalis' : (0, 25),
        'western-wa-sw-bc' : (0, 80),
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
    '24-hour-precip' : 'pcp24',
    'surface-temp' : 'tsfc',
    '10m-wind-speed' : 'wssfc2',
    'integrated-cloud' : 'intcld'
}
expected_hours = {
    '12km' : {
        '24-hour-precip' : [h for h in range(24, 180, 12)],
        '3-hour-precip' : [h for h in range(6, 183, 3) if h != 3],  # not sure why these all start at 6, but I think there was a reason
        'surface-temp' : [h for h in range(24, 180, 12)],
        '10m-wind-speed' : [h for h in range(24, 180, 12)],
        'integrated-cloud' : [h for h in range(6, 183, 3) if h != 3],
    },
    '4km' : {
        '3-hour-precip' : [h for h in range(6, 84, 3) if h != 3],
        'surface-temp' : [h for h in range(6, 84, 3) if h != 3],
        '10m-wind-speed' : [h for h in range(6, 84, 3) if h != 3],
        'integrated-cloud' : [h for h in range(6, 84, 3) if h != 3],
    },
    '1.33km' : {
        '3-hour-precip' : [h for h in range(6, 72, 3) if h != 3],
        'surface-temp' : [h for h in range(6, 72, 3) if h != 3],
        '10m-wind-speed' : [h for h in range(6, 72, 3) if h != 3],
        'integrated-cloud' : [h for h in range(6, 72, 3) if h != 3],
    }
}

final_image_params = {
    'margin' : 10,
    'columns' : 10
}

htmlheader = """<!DOCTYPE html>
<html>
<body style="background-color:black;">
"""
htmlfooter = """</body>
</html>
"""

# ----------------------------------------------------------------------------------------
def get_subimage(img, rname, margins):
    tmpco = {side : margins[rname][iside] for side, iside in side_indices.items()}
    width, height = img.size
    bbox = (tmpco['left'], tmpco['top'], width - tmpco['right'], height - tmpco['bottom'])
    subimg = img.crop(bbox)
    if rname in rescale_pixels:  # doesn't work for shit (well, it's too few pixels so it's hard to read the date)
        subimg = subimg.resize(rescale_pixels[rname]) #, resample=Image.LANCZOS)
    return subimg

# ----------------------------------------------------------------------------------------
def get_url(domain, maptype, variable, hour):
    return base_url + '/images_' + domain_codes[domain] + '/' + maptype_codes[maptype] + variable_codes[variable] + '.' + ('%02d' % hour) + '.0000.gif'

# ----------------------------------------------------------------------------------------
def get_legend_fname(maptype, variable):
    if 'precip' in variable:
        variable_category = 'precip'
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
def get_single_date(img):
    try:
        datestr = str(pytesseract.image_to_string(img))
        # img.save(os.getenv('www') + '/tmp/tmp.png')
        # sys.exit()
    except:
        print '  failed running tesseract'
        return None
    else:
        try:
            # old version for full non-init date line:
            # datelist = datestr[datestr.find('(') + 1 : datestr.find(')')].replace('\'', '').split()
            # new version for init time:
            datelist = datestr.translate(None, '_\'\"();:{}').split()
            if 'UTC' not in datelist:
                print '  \'UTC\' not found in %s' % datestr
                return None
            utc_str_index = datelist.index('UTC')  # index of the string \'UTC\'
            datelist = datelist[utc_str_index - 1 : ]  # i.e. trim off the 'Init:'
            dateinfo = {}
            for ifmt in range(len(expected_date_format)):
                dateinfo[expected_date_format[ifmt]] = datelist[ifmt]
            convert_dateinfo(dateinfo)
            imonth = list(calendar.month_abbr).index(dateinfo['month'])
            utc_init_time = datetime.datetime(dateinfo['year'], imonth, dateinfo['monthday'], dateinfo['hours'])
            utc_init_time = utc_init_time.replace(tzinfo=tz.gettz('UTC'))  # tell the datetime object that it's in UTC time zone since datetime objects are 'naive' by default
            pdt_init_time = utc_init_time.astimezone(tz.gettz('PDT'))
        except Exception, e:
            print '  couldn\'t convert tesseract output string \'%s\'' % datestr
            print e
            return None
    return pdt_init_time

# ----------------------------------------------------------------------------------------
def set_dates(imgfo):
    # first find one date that we can get
    init_time = None
    for iimg in range(len(imgfo)):
        if init_time is None:
            init_time = get_single_date(imgfo[iimg]['subimages']['init-time'])
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
        img = Image.open(fname)
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
def get_links(all_fnames):
    fnames = sorted(all_fnames)
    links = []
    last_domain = None
    for fname in fnames:
        domain, variable = reverse_htmlfname(fname)
        linkstr = '<a href="' + fname + '"><font size=3>' + variable.replace('-', ' ') + '</font></a>'
        if last_domain is None or domain != last_domain:
            linkstr = '<font color=white>' + domain + ': </font>' + linkstr
        if last_domain is not None and domain != last_domain:
            linkstr = '<br>\n' + linkstr
        links.append(linkstr)
        last_domain = domain
    return links

# ----------------------------------------------------------------------------------------
def write_index_html(fname, all_fnames):
    with open(fname, 'w') as htmlfile:
        htmlfile.write(htmlheader)
        for link in get_links(all_fnames):
            htmlfile.write(link + '\n')
        htmlfile.write(htmlfooter)

# ----------------------------------------------------------------------------------------
def add_linkstrs(fname, all_fnames):
    with open(args.outdir + '/' + fname) as htmlfile:
        lines = htmlfile.readlines()
    with open(args.outdir + '/' + fname, 'w') as htmlfile:
        for line in lines:
            if '<body' in line:
                # htmlfile.write('<center>\n')
                for link in get_links(all_fnames):
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
    if tzstr != 'PDT':
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
        urllib.urlretrieve(front_page_url, tmpfile.name)
        tree = etree.parse(tmpfile, parser)
    if cachefname is not None:  # write html to a file in case we want it later
        if debug:
            print '    writing html to %s' % cachefname
        tmpstr = etree.tostring(tree.getroot(), pretty_print=True, method='html')
        with open(cachefname, 'w') as tmpfile:
            tmpfile.write(tmpstr)

    tdlist = list(tree.findall('.//td'))
    run_time, status_time = get_run_status_times(tdlist[0])
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
wrfdir = os.path.dirname(os.path.realpath(__file__))
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

    run()

    if not args.no_push:
        check_call([wrfdir + '/upload.sh', args.outdir.replace('/wrfparser', '')])
        if not args.no_sleep:
            time.sleep(just_finished_sleep_time)

    if args.test or args.no_sleep:
        break
