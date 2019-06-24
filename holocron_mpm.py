import subprocess
import time
import datetime as dt
import pyautogui
from slackclient import SlackClient
from pywinauto.findwindows import find_window
from pywinauto.win32functions import SetForegroundWindow
from pywinauto import MatchError
from PIL import ImageGrab
import os
import math

config = open('config.txt', 'r')
lines = config.readlines()  # get the data for the local bot version - the items in config.txt will vary between different installations
"""
line 0:  bot name in plaintext, required only for initial setup.
line 1:  bot UID from the Slack API, you can find this by providing print_bot_id.py with the API Token from Slack.
line 2:  Bot API token, unique for each bot, needed to connect to the Slack API network.
line 3:  email account name for legacy version of holocron.
line 4:  email password for legacy version of holocron.
line 5:  file path for multipool miner exe
"""

config.close()

new_lines = []
for line in lines:
    new_lines.append(line[:-1])  # pop off that pesky newline escape character
lines = new_lines

bot_id = lines[1]
slack_client = SlackClient(lines[2])

DEFAULT_CHANNEL = 'C895B0JDT'  # default channel ID for rig monitor output

at_bot = '<@' + bot_id + '>'  # bot UID as output by Slack API - stream of digits enclosed by carrot brackets -- <@123456>

upload = "uploaded"  # used to pass through the message posted when the bot uploads a screencap
checkin_message = "online!"  # used to pass the checkin greeting bots post when coming online
example_command = "doodley"
screencap = "screencap"
commands = "commands"
start = "start"
close = "close"
shutdown = "shutdown"
reboot = "reboot"
uptime = "uptime"
downtime = "downtime"


def handle_command(command, channel, session_string):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = (
        "Not sure what you mean. Use the *" +
        example_command +
        "* command with numbers, delimited by spaces.")
    if command.startswith(upload) or command.startswith(checkin_message):
        # Early Exit to ignore chats posted when the bot uploads a screenshot
        # This would ordinarily trip the chat parser with its' own output.
        return session_string
    elif command.startswith(example_command):
        response = "Sure...write some more code then I can do that!"
    elif command.startswith(screencap):

        if send_screenshot():
            slack_client.api_call("chat.postMessage", channel=channel,
                                  text="Here's that screencap.", as_user=True)
            return session_string
        else:
            slack_client.api_call("chat.postMessage", channel=channel,
                                  text="MPM is not running!", as_user=True)

            return session_string
    elif command.startswith(commands):
        response = "`do`  Example command; does nothing.\n"
        response += "`commands`  Displays a list of commands and their functions.\n"
        response += "`screencap`  Brings the Miner window to the front, and uploads a screen capture to the channel.\n"
        response += "`start`  *Starts* Miner if it's closed, and starts it mining if it's stopped.\n"
        response += "`stop` *Stops* Miner if it is open / mining.\n"
        response += "`close`  *Closes* Miner\n"
        response += "`shutdown`  *Shutdown* the PC.  *NO WAY TO REMOTE RESTART.*\n"
        response += "`reboot`  *Reboot* the PC."
        response += "'uptime' report consecutive uptime for session"
        response += "'downtime' report total downtime in seconds, rounded to the nearest uptime ping (every 5mins), for 24/72/168hr periods"
    elif command.startswith(start):
        session_string = start_miner()
        response = "MPM started"
    elif command.startswith(close):
        if not miner_exe_running():
            slack_client.api_call("chat.postMessage", channel=channel,
                                  text="MPM not running!", as_user=True)
            session_string = None
            return session_string
        terminate_miner()
        session_string = None
        response = "MPM terminated."

    elif command.startswith(uptime):
        if not session_string:
            response = "MPM is down, no uptime this session."
        else:
            uptime_seconds = check_uptime(session_string)
            response = "Uptime this session: {0}s".format(uptime_seconds)
    elif command.startswith(downtime):
        downtime_seconds = check_downtime(session_string)
        response = "Downtime 24hr: {0}s / 72hr: {1}s / 168hr: {2}s".format(
            downtime_seconds[0],
            downtime_seconds[1],
            downtime_seconds[2])
    elif command.startswith(shutdown):
        slack_client.api_call("chat.postMessage", channel=channel,
                              text="Shutting down...", as_user=True)
        shutdown_system()
        return session_string
    elif command.startswith(reboot):
        slack_client.api_call("chat.postMessage", channel=channel,
                              text="Rebooting...", as_user=True)
        reboot_system()
        return session_string

    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)
    return session_string


def format_date(date):
    formatted_date = date.strftime("{0:02}-{1:02}-{2}_{3:02}{4:02}{5:02}".format(
        date.month,
        date.day,
        date.year,
        date.hour,
        date.minute,
        date.second))
    return formatted_date


def send_screenshot():
    def take_screenshot(date_string):
        SetForegroundWindow(find_window(best_match="holocron_mpm.py"))
        ImageGrab.grab().save("screenshots/{0}.png".format(date_string), "PNG")
    if not miner_exe_running():
        return False
    date = dt.datetime.now()
    date_string = format_date(date)
    take_screenshot(date_string)
    slack_client.api_call('files.upload',
                          channels=channel,
                          filename='{0}.png'.format(date_string),
                          file=open('screenshots/{0}.png'.format(date_string), 'rb'))
    return True


def check_uptime(session_string):
    session_logfile = open("holocron_logs/{0}".format(session_string), 'r')
    start_time = dt.datetime.strptime(session_logfile.readlines()[0][:-1], '%c')
    current_time = dt.datetime.now()
    uptime_in_seconds = (current_time - start_time).total_seconds()
    session_logfile.close()
    return math.floor(uptime_in_seconds)


def check_cum_downtime(session_string):
    current_time = dt.datetime.now()
    one_day = 86400
    three_days = 259200
    seven_days = 604800
    a = 0
    b = 0
    c = 0
    if not os.listdir('holocron_logs'):
        return one_day, three_days, seven_days
    for log_name in sorted(os.listdir('holocron_logs')):
        open_log = open("holocron_logs/{0}".format(log_name), 'r')
        pings = open_log.readlines()
        last_ping = pings[-1][:-1]
        ping_age = (
            dt.datetime.strptime(last_ping, '%c') - current_time).total_seconds()
        if ping_age < one_day and os.listdir('holocron_logs').index(log_name) + 1 < len(os.listdir('holocron_logs')):
            next_log_name = os.listdir('holocron_logs')[os.listdir('holocron_logs').index(log_name) + 1]
            next_log = open('holocron_logs/{0}'.format(next_log_name), 'r')
            next_start_time = next_log.readlines()[0][:-1]
            next_log.close()
            a += (dt.datetime.strptime(next_start_time, '%c') - dt.datetime.strptime(last_ping, '%c')).total_seconds()
        if ping_age < three_days and os.listdir('holocron_logs').index(log_name) + 1 < len(os.listdir('holocron_logs')):
            next_log_name = os.listdir('holocron_logs')[os.listdir('holocron_logs').index(log_name) + 1]
            next_log = open('holocron_logs/{0}'.format(next_log_name), 'r')
            next_start_time = next_log.readlines()[0][:-1]
            next_log.close()
            b += (dt.datetime.strptime(next_start_time, '%c') - dt.datetime.strptime(last_ping, '%c')).total_seconds()
        if ping_age < seven_days and os.listdir('holocron_logs').index(log_name) + 1 < len(os.listdir('holocron_logs')):
            next_log_name = os.listdir('holocron_logs')[os.listdir('holocron_logs').index(log_name) + 1]
            next_log = open('holocron_logs/{0}'.format(next_log_name), 'r')
            next_start_time = next_log.readlines()[0][:-1]
            c += (dt.datetime.strptime(next_start_time, '%c') - dt.datetime.strptime(last_ping, '%c')).total_seconds()
        open_log.close()
    if not session_string:
        last_log_name = sorted(os.listdir('holocron_logs'))[-1]
        last_logfile = open('holocron_logs/{0}'.format(last_log_name), 'r')
        pings = last_logfile.readlines()
        last_ping_time = dt.datetime.strptime(pings[-1][:-1], '%c')
        ping_age = (current_time - last_ping_time).total_seconds()
        print(ping_age)
        a += min(ping_age, one_day)
        b += min(ping_age, three_days)
        c += min(ping_age, seven_days)
    return math.floor(a), math.floor(b), math.floor(c)


def uptime_ping(session_string):
    if not miner_exe_running():
        return
    date = dt.datetime.now()
    session_logfile = open("holocron_logs/{0}".format(session_string), 'a')
    session_logfile.write("{0}\n".format(date.strftime('%c')))
    session_logfile.close()


def check_downtime(session_string):
    if miner_exe_running():
        return False
    if not os.listdir('holocron_logs'):
        return False
    current_time = dt.datetime.now()
    last_log_name = sorted(os.listdir('holocron_logs'))[-1]
    last_logfile = open('holocron_logs/{0}'.format(last_log_name), 'r')
    pings = last_logfile.readlines()
    last_ping_time = dt.datetime.strptime(pings[-1][:-1], '%c')
    ping_age = (current_time - last_ping_time).total_seconds()
    if ping_age > 900:
        return True
    return False


def terminate_miner():
    SetForegroundWindow(find_window(best_match="holocron_mpm.py"))
    pyautogui.keydown(['ctrlleft'])
    time.sleep(0.05)
    pyautogui.keydown(['c'])
    time.sleep(0.05)
    pyautogui.keyup(['ctrlleft'])
    pyautogui.keyup(['c'])
    return None


def miner_exe_running():
    try:
        SetForegroundWindow(find_window(best_match="holocron_mpm.py"))
    except MatchError:
        return False
    return True


def start_miner():
    subprocess.Popen("Start.bat")
    date = dt.datetime.now()
    session_string = "{0}.log".format(format_date(date))
    session_logfile = open("holocron_logs/{0}".format(session_string), 'w')
    session_logfile.write("{0}\n".format(date.strftime('%c')))
    session_logfile.close()
    return session_string


def checkin():
    checkin_greeting = at_bot + "online!"
    slack_client.api_call("chat.postMessage", channel=DEFAULT_CHANNEL,
                          text=checkin_greeting, as_user=True)


def reboot_system():
    print("Rebooting")
    pyautogui.typewrite(['winleft'])
    time.sleep(0.5)
    pyautogui.typewrite(['right', 'right', 'r'])


def shutdown_system():
    print("Shutting Down")
    pyautogui.typewrite(['winleft'])
    time.sleep(0.5)
    pyautogui.typewrite(['right', 'enter'])


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and at_bot in output['text']:
                return output['text'].split(at_bot)[1].strip().lower(), output['channel']
            elif output and 'text' in output and '<!channel>' in output['text']:
                return output['text'].split('<!channel>')[1].strip().lower(), output['channel']
    return None, None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("holocron established connection with slack.")
        checkin()
        session_string = start_miner()
        ping_interval = 300
        last_ping = dt.datetime.now()
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                session_string = handle_command(command, channel, session_string)
            time.sleep(READ_WEBSOCKET_DELAY)
            current_time = dt.datetime.now()
            if (current_time - last_ping).total_seconds() > ping_interval:
                uptime_ping(session_string)
                downtime_flag = check_downtime(session_string)
                if downtime_flag:
                    slack_client.api_call("chat.postMessage", channel=DEFAULT_CHANNEL,
                                          text="Rig down for over 15 minutes!", as_user=True)

    else:
        print("Connection failed. Invalid Slack token or bot ID?")
