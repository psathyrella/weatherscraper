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

front_page_url = 'http://www.atmos.washington.edu/mm5rt'
model_strings = ('WRF-GFS', 'Extended WRF-GFS')

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
        dateinfo[key] = dateinfo[key].replace('O', '0').replace('l', '1').replace('(', '')
        dateinfo[key] = int(dateinfo[key])
    dateinfo['year'] += 2000

typical_hours_between_init_and_zero_fcast_hour = 4
side_indices = {'left' : 0, 'right' : 1, 'top' : 2, 'bottom' : 3}
base_margins = {  # (left, right, top, bottom)
    'full' : (0, 0, 0, 0),
    'init-time' : (500, 0, 0, 875),
    'entire-date-line' : (0, 0, 21, 855),
    'right-legend' : (850, 3, 100, 70)
}
specific_margins = {  # (left, right, top, bottom)
    'washington-plus' : {
        'date' : (630, 123, 21, 855),
        'full-date' : (630, 5, 21, 855),
        'western-wa-sw-bc' : (275, 430, 270, 350)
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
    }
}
# ----------------------------------------------------------------------------------------
def get_margins(maptype):
    margins = base_margins.copy()
    margins.update(specific_margins[maptype])
    return margins
    
paste_sizes = {
    'washington-plus' : (200, 300),
    'pacific-northwest' : (180, 260),
    'washington' : (175, 460),
    'western-washington' : (280, 604)
}
# rescale_pixels = {
#     'full-date' : (150, 20)
# }

paste_positions = {
    'washington-plus' : {
        'full-date' : (0, 0),
        'western-wa-sw-bc' : (0, 28)
    },
    'pacific-northwest' : {
        'date' : (0, 0),
        'western-wa-sw-bc' : (0, 28)
    },
    'washington' : {
        'date' : (0, 0),
        'howe-to-chehalis' : (0, 28),
        'cascades' : (0, 107)
    },
    'western-washington' : {
        'full-date' : (0, 0),
        'cascades' : (0, 30)
    }
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
    'western-washington' : 'ww_'
}
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
        'surface-temp' : [h for h in range(24, 180, 12)],
        '10m-wind-speed' : [h for h in range(24, 180, 12)]
    },
    '4km' : {
        '3-hour-precip' : [h for h in range(6, 84, 3) if h != 3],
        'surface-temp' : [h for h in range(6, 84, 3) if h != 3],
        '10m-wind-speed' : [h for h in range(6, 84, 3) if h != 3],
        'integrated-cloud' : [h for h in range(6, 84, 3) if h != 3]
    },
    '1.33km' : {
        '3-hour-precip' : [h for h in range(6, 72, 3) if h != 3],
        'surface-temp' : [h for h in range(6, 72, 3) if h != 3],
        '10m-wind-speed' : [h for h in range(6, 72, 3) if h != 3],
        'integrated-cloud' : [h for h in range(6, 72, 3) if h != 3]
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
    # if rname in rescale_pixels:
    #     subimg = subimg.resize(rescale_pixels[rname])
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
    joined_image = Image.new("RGB", paste_sizes[maptype])
    for name, ppos in paste_positions[maptype].items():
        joined_image.paste(subimages[name], ppos)
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
        datestr = pytesseract.image_to_string(img)
    except:
        print '  failed running tesseract'
        return None
    else:
        try:
            # old version for full non-init date line:
            # datelist = datestr[datestr.find('(') + 1 : datestr.find(')')].replace('\'', '').split()
            # new version for init time:
            datelist = datestr.replace('_', '').split()  # tesseract seems to lose the 'Init:' for some reason
            dateinfo = {}
            for ifmt in range(len(expected_date_format)):
                dateinfo[expected_date_format[ifmt]] = datelist[ifmt]
            convert_dateinfo(dateinfo)
            imonth = list(calendar.month_abbr).index(dateinfo['month'])
            utc_init_time = datetime.datetime(dateinfo['year'], imonth, dateinfo['monthday'], dateinfo['hours'])
            utc_init_time = utc_init_time.replace(tzinfo=tz.gettz('UTC'))  # tell the datetime object that it's in UTC time zone since datetime objects are 'naive' by default
            pdt_init_time = utc_init_time.astimezone(tz.gettz('PDT'))
        except:
            print '  couldn\'t convert tesseract output string \'%s\'' % datestr
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
    # subimages['init-time'].save('tmp.png')
    # sys.exit()

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
            if domain != '12km' and last_weekday is not None and imgfo[ifn]['datetime'].weekday() != last_weekday:
                htmlfile.write('<br>\n')
            last_weekday = imgfo[ifn]['datetime'].weekday()
            htmlfile.write('<a href="' + get_fname(domain, maptype, variable, imgfo[ifn]['fcast-hour'], processed=False) + '"> <img alt="foop", src="' + get_fname(domain, maptype, variable, imgfo[ifn]['fcast-hour'], processed=True) + '", width="150"> </a>\n')
        htmlfile.write('<br>\n')
        htmlfile.write('<center><a href="' + get_legend_fname(maptype, variable) + '"><img src="' + get_legend_fname(maptype, variable) + '", width="' + ('500' if 'wind' in variable else '350') + '"></a></center>\n')
        htmlfile.write(htmlfooter)

# ----------------------------------------------------------------------------------------
def get_status(modeltype, cachefname=None):
    # note: you really don't want to download images while the fcasts are running, since they go through their file system gradually replacing files as they run (i.e. you'll download an inconsistent series of images)
    parser = etree.HTMLParser()

    # tree = etree.parse(cachefname, parser)
    try:
        tree = etree.parse(front_page_url, parser)
        if cachefname is not None:  # write html to a file in case we want it later
            tmpstr = etree.tostring(tree.getroot(), pretty_print=True, method='html')
            with open(cachefname, 'w') as tmpfile:
                tmpfile.write(tmpstr)
        txtlist = [td.text.strip() for td in tree.findall('.//td') if td.text is not None and td.text.strip() != '']
    except:
        print '    failed parsing etree for %s' % front_page_url
        return 'unknown'

    for itd in range(len(txtlist)):
        txt = txtlist[itd]
        if txt == modeltype:  # shold look like [..., 'WRF-GFS', 'Status', 'complete', ...]  (or not complete, if it ain't complete)
            if itd >= len(txtlist) - 1 or txtlist[itd + 1] != 'Status':
                return 'unknown'
            if itd >= len(txtlist) - 2:
                return 'unknown'
            status_text = txtlist[itd + 2]
            if status_text == 'complete':
                return 'complete'
            elif status_text == 'not yet begun' \
                 or 'complete through forecast hour' in status_text \
                 or 'not begun' in status_text \
                 or ('finished with the' in status_text and 'to hr' in status_text):
                     return 'running'
            else:
                print '\nnot sure about status: \'%s\', returning \'running\'' % txtlist[itd + 2]
                return 'running'

    return 'unknown'

# ----------------------------------------------------------------------------------------
def check_all_models_complete():
    if args.test:
        return True

    cachedir = wrfdir + '/_cache'
    if not os.path.exists(cachedir):
        os.makedirs(cachedir)

    statuses = []
    for mstr in model_strings:
        cachefname = cachedir + '/%s-%s-status.html' % (mstr, datetime.datetime.now().__str__().replace(' ', '_'))
        statuses.append(get_status(mstr, cachefname=cachefname))
        if statuses[-1] == 'unknown':
            print 'unknown status for %s, wrote html to %s' % (mstr, cachefname)
            return False
        else:
            if os.path.exists(cachefname):
                os.remove(cachefname)
            else:
                print 'wtf? cache file %s doesn\'t exist' % cachefname
            if statuses[-1] == 'running':
                return False
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

if args.test:
    args.no_sleep = True
    args.no_download = True
    args.no_push = True

while True:
    all_complete = check_all_models_complete()
    while not args.no_sleep and not all_complete:
        print '  forecasts are running, sleep for a bit'
        time.sleep(1800)  # 1800s is 30m
        all_complete = check_all_models_complete()

    run()

    if not args.no_push:
        check_call([wrfdir + '/upload.sh', args.outdir.replace('/wrfparser', '')])
        time.sleep(21600)  # 21600s is 6h
