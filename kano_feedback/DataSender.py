#!/usr/bin/env python

# DataSender.py
#
# Copyright (C) 2014 Kano Computing Ltd.
# License: http://www.gnu.org/licenses/gpl-2.0.txt GNU General Public License v2
#
# Functions related to sending feedback data
#

import os
from os.path import expanduser
import datetime
import json
from gi.repository import Gtk

import kano.logging as logging
from kano.utils import run_cmd, write_file_contents, ensure_dir, delete_dir, delete_file, \
    read_file_contents
from kano_world.connection import request_wrapper
from kano_world.functions import get_email, get_mixed_username
from kano_profile.badges import increment_app_state_variable_with_dialog
from kano.logging import logger
from kano.gtk3.kano_dialog import KanoDialog
from kano_world.functions import is_registered
from kano.network import is_internet

TMP_DIR = os.path.join(expanduser('~'), '.kano-feedback/')
SCREENSHOT_NAME = 'screenshot.png'
SCREENSHOT_PATH = TMP_DIR + SCREENSHOT_NAME


def send_data(text, fullInfo, subject=""):
    files = {}

    if fullInfo:
        files['report'] = get_metadata_archive()

    payload = {
        "text": text,
        "email": get_email(),
        "category": "os",
        "subject": subject
    }

    # send the bug report and remove all the created files
    success, error, data = request_wrapper('post', '/feedback', data=payload, files=files)
    delete_tmp_dir()

    if not success:
        return False, error
    if fullInfo:
        # kano-profile stat collection
        increment_app_state_variable_with_dialog('kano-feedback', 'bugs_submitted', 1)

        # logs were sent, clean up
        logging.cleanup()

    return True, None


def delete_tmp_dir():
    delete_dir(TMP_DIR)


def create_tmp_dir():
    ensure_dir(TMP_DIR)


def delete_screenshot():
    delete_file(SCREENSHOT_PATH)


def get_metadata_archive():
    ensure_dir(TMP_DIR)

    file_list = [
        {'name': 'kanux_version.txt', 'contents': get_version()},
        {'name': 'process.txt', 'contents': get_processes()},
        {'name': 'packages.txt', 'contents': get_packages()},
        {'name': 'dmesg.txt', 'contents': get_dmesg()},
        {'name': 'syslog.txt', 'contents': get_syslog()},
        {'name': 'cmdline.txt', 'contents': read_file_contents('/boot/cmdline.txt')},
        {'name': 'config.txt', 'contents': read_file_contents('/boot/config.txt')},
        {'name': 'wifi-info.txt', 'contents': get_wifi_info()},
        {'name': 'ifconfig.txt', 'contents': get_networks_info()},
        {'name': 'usbdevices.txt', 'contents': get_usb_devices()},

        # TODO: Remove raw logs when json ones become stable
        {'name': 'app-logs.txt', 'contents': get_app_logs_raw()},

        {'name': 'app-logs-json.txt', 'contents': get_app_logs_json()},
        {'name': 'hdmi-info.txt', 'contents': get_hdmi_info()}
    ]

    if os.path.isfile(SCREENSHOT_PATH):
        file_list.append({
                         'name': SCREENSHOT_NAME,
                         'contents': read_file_contents(SCREENSHOT_PATH)
                         })

    # create files for each non empty metadata info
    for file in file_list:
        if file['contents']:
            write_file_contents(TMP_DIR + file['name'], file['contents'])

    # archive all the metadata files - need to change dir to avoid tar subdirectories
    archive_path = 'bug_report.tar.gz'
    current_directory = os.getcwd()
    os.chdir(TMP_DIR)
    run_cmd("tar -zcvf {} *".format(archive_path))

    # open the file and return it
    archive = open(archive_path, 'rb')

    # restore the current working directory
    os.chdir(current_directory)
    return archive


def get_version():
    cmd = "ls -l /etc/kanux_version | awk '{ print $6 \" \" $7 \" \" $8 }' && cat /etc/kanux_version"
    o, _, _ = run_cmd(cmd)
    return o


def get_processes():
    cmd = "ps -aux"
    o, _, _ = run_cmd(cmd)
    return o


def get_packages():
    cmd = "dpkg-query -l | awk '{ print $2 \"-\" $3 }'"
    o, _, _ = run_cmd(cmd)
    return o


def get_dmesg():
    cmd = "dmesg"
    o, _, _ = run_cmd(cmd)
    return o


def get_syslog():
    cmd = "tail -v -n 100 /var/log/messages"
    o, _, _ = run_cmd(cmd)
    return o


def get_wpalog():
    cmd = "tail -n 300 /var/log/kano_wpa.log"
    o, _, _ = run_cmd(cmd)
    return o


def get_wlaniface():
    cmd = "iwconfig wlan0"
    o, _, _ = run_cmd(cmd)
    return o


def get_app_logs_raw():
    logs = logging.read_logs()

    # Extract kano logs in raw format. "LOGFILE: component", one line per component,
    # followed by entries in the form: "2014-09-30T10:18:54.532015 kano-updater info: Return value: 0"
    output = ""
    for f, data in logs.iteritems():
        app_name = os.path.basename(f).split(".")[0]
        output += "LOGFILE: {}\n".format(f)
        for line in data:
            line["time"] = datetime.datetime.fromtimestamp(line["time"]).isoformat()
            output += "{time} {app} {level}: {message}\n".format(app=app_name, **line)

    return output


def get_app_logs_json():
    # Fetch the kano logs
    kano_logs=logging.read_logs()

    # Transform them into a sorted, indented json stream
    kano_logs_json=json.dumps(kano_logs, sort_keys=True, indent=4, separators=(',', ': '))
    return kano_logs_json


def get_kwifi_cache():
    # We do not collect sensitive private information - Keypass is sent as "obfuscated" literal
    cmd = "cat /etc/kwifiprompt-cache.conf | sed 's/\"enckey\":.*/\"enckey\": \"obfuscated\"/'"
    o, _, _ = run_cmd(cmd)
    return o


def get_usb_devices():
    # Gives us 2 short lists of usb devices, first one with deviceIDs and manufacturer strings
    # Second one in hierarchy mode along with matching kernel drivers controlling each device
    # So we will know for a wireless dongle which kernel driver linux decides to load. Same for HIDs.
    cmd = "lsusb && lsusb -t"
    o, _, _ = run_cmd(cmd)
    return o


def get_networks_info():
    cmd = "ifconfig"
    o, _, _ = run_cmd(cmd)
    return 0


def get_wifi_info():
    # Get username here
    world_username = "Kano World username: {}\n\n".format(get_mixed_username())
    kwifi_cache = "**kwifi_cache**\n {}\n\n".format(get_kwifi_cache())
    wlaniface = "**wlaniface**\n {}\n\n".format(get_wlaniface())
    wpalog = "**wpalog**\n {}\n\n".format(get_wpalog())
    return world_username + kwifi_cache + wlaniface + wpalog


def get_hdmi_info():
    # Current resolution
    cmd = "tvservice -s"
    o, _, _ = run_cmd(cmd)
    res = 'Current resolution: {}\n\n'.format(o)
    # edid file
    file_path = TMP_DIR + 'edid.dat'
    cmd = "tvservice -d {} && edidparser {}".format(file_path, file_path)
    edid, _, _ = run_cmd(cmd)
    delete_file(file_path)
    return res + edid


def take_screenshot():
    ensure_dir(TMP_DIR)
    cmd = "kano-screenshot -w 1024 -p " + SCREENSHOT_PATH
    _, _, rc = run_cmd(cmd)


def copy_screenshot(filename):
    ensure_dir(TMP_DIR)
    if os.path.isfile(filename):
        run_cmd("cp %s %s" % (filename, SCREENSHOT_PATH))


def sanitise_input(text):
    # Replace double quotation mark for singles
    text = text.replace('"', "'")
    # Fix upload error when data field begins with " or '
    if text[:1] == '"' or text[:1] == "'":
        text = " " + text
    return text


def try_login():
    # Check if user is registered
    if not is_registered():
        _, _, rc = run_cmd('kano-login 3')

    return is_registered()


def try_connect():
    if is_internet():
        return True

    run_cmd('sudo /usr/bin/kano-settings 12')

    return is_internet()


def send_form(title, body):
    if not try_connect() or not try_login():
        KanoDialog('Unable to send',
                   'Please check that you have internet and ' +
                   'are logged into Kano World.').run()
        return False

    # Send Google Form
    dataToSend = ''
    # Question entry
    dataToSend += 'entry.55383705'
    dataToSend += '='
    dataToSend += sanitise_input(title)
    dataToSend += '&'
    # User entry
    dataToSend += 'entry.226915453'
    dataToSend += '='
    dataToSend += sanitise_input(get_mixed_username())
    dataToSend += '&'
    # Reply entry
    dataToSend += 'entry.2017124825'
    dataToSend += '='
    dataToSend += sanitise_input(body)
    dataToSend += '&'
    # Email entry
    dataToSend += 'entry.31617144'
    dataToSend += '='
    dataToSend += sanitise_input(get_email())
    dataToSend += '&'
    # Send data
    form = 'https://docs.google.com/a/kano.me/forms/d/1FH-6IKeuc9t6pp4lPhncG1yz29lYuLGpFv88RRaUBgU/formResponse'
    cmd = 'curl --progress-bar -d \"%s\" %s' % (dataToSend, form)
    o, e, rc = run_cmd(cmd)

    if rc != 0:
        logger.error('Error while sending feedback: {}'.format(e))
        retry = KanoDialog(
            'Unable to send',
            'Error while sending your feedback. Do you want to retry?',
            button_dict={
                'CLOSE FEEDBACK':
                    {
                        'return_value': False,
                        'color': 'red'
                    },
                'RETRY':
                    {
                        'return_value': True,
                        'color': 'green'
                    }
            }
        )

        if retry.run():
            # Try again until they say no
            send_form(title, body)

        return False

    thank_you = KanoDialog('Thank You',
                           'Your feedback is very important to us.')
    thank_you.dialog.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
    thank_you.run()

    return True
