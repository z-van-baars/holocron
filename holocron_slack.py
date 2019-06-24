import subprocess
import time
import datetime
import pyautogui
from slackclient import SlackClient
from pywinauto.findwindows import find_window
from pywinauto.win32functions import SetForegroundWindow
from pywinauto import MatchError
from PIL import ImageGrab

config = open('config.txt', 'r')
lines = config.readlines()  # get the data for the local bot version - the items in config.txt will vary between different installations
"""
line 0:  bot name in plaintext, required only for initial setup.
line 1:  bot UID from the Slack API, you can find this by providing print_bot_id.py with the API Token from Slack.
line 2:  Bot API token, unique for each bot, needed to connect to the Slack API network.
line 3:  email account name for legacy version of holocron.
line 4:  email password for legacy version of holocron.
line 5:  file path for NiceHash Miner 2.exe
line 6:  File path for Vertcoin OCM exe
"""

config.close()

new_lines = []
for line in lines:
    new_lines.append(line[:-1])  # pop off that pesky newline escape character
lines = new_lines

bot_id = lines[1]
slack_client = SlackClient(lines[2])

DEFAULT_CHANNEL = 'C895B0JDT'  # default channel ID for rig monitor output
NH_WINDOW_W = 630  # fixed window width for NiceHash Miner
NH_WINDOW_H = 440  # fixed window height
OCM_WINDOW_W = 434
OCM_WINDOW_H = 335

at_bot = '<@' + bot_id + '>'  # bot UID as output by Slack API - stream of digits enclosed by carrot brackets -- <@123456>

upload = "uploaded"  # used to pass through the message posted when the bot uploads a screencap
checkin_message = "online!"  # used to pass the checkin greeting bots post when coming online
example_command = "do"
screencap = "screencap"
commands = "commands"
start = "start"
stop = "stop"
close = "close"
shutdown = "shutdown"
reboot = "reboot"

mining_exe_selected = False
while not mining_exe_selected:
    active_mining_exe = (input("Start in which mode? (N)iceHash, (V)ertcoin: ")).lower()
    print(active_mining_exe)
    if active_mining_exe == "v" or active_mining_exe == "n":
        mining_exe_selected = True
        if active_mining_exe == "v":
            print("Vertcoin mining software selected.")
        elif active_mining_exe == "n":
            print("Nicehash mining software selected.")
    else:
        print("please input selection again.")


class MinerExe(object):
    def __init__(self,
                 name,
                 window_width,
                 window_height,
                 process_name,
                 start_offset,
                 stop_offset,
                 close_offset,
                 dir_name,
                 process_path):
        self.name = name
        self.window_width = window_width
        self.window_height = window_height
        self.process_name = process_name
        self.start_offset = start_offset
        self.stop_offset = stop_offset
        self.close_offset = close_offset
        self.dir_name = dir_name
        self.process_path = process_path


class VertCoinOCM(MinerExe):
    def __init__(self):
        super().__init__("Vertcoin OCM",
                         434,  # miner ui window width
                         335,  # miner ui window height
                         "Vertcoin OCM",
                         (23, 10),  # start offset
                         (23, 10),  # stop offset
                         (67, 25),  # close offset
                         "vertcoin",
                         lines[6])  # exe path


class NiceHash(MinerExe):
    def __init__(self):
        super().__init__("NiceHash Miner",
                         630,  # miner ui window width
                         440,  # miner ui window height
                         "NiceHash Miner",
                         (36, 36),  # start offset
                         (30, -60),  # stop offset
                         (62, 27),  # close offset
                         "nicehash",
                         lines[5])  # exe path


if active_mining_exe == "v":
    active_miner_exe = VertCoinOCM()
elif active_mining_exe == "n":
    active_miner_exe = NiceHash()


def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = "Not sure what you mean. Use the *" + example_command + "* command with numbers, delimited by spaces."
    if command.startswith(upload) or command.startswith(checkin_message):
        # Early Exit to ignore chats posted when the bot uploads a screenshot, this would ordinarily trip the chat parser.
        return
    elif command.startswith(example_command):
        response = "Sure...write some more code then I can do that!"
    elif command.startswith(screencap):

        if send_screenshot(active_miner_exe):
            slack_client.api_call("chat.postMessage", channel=channel,
                                  text="Here's that screencap.", as_user=True)
            return
        else:
            slack_client.api_call("chat.postMessage", channel=channel,
                                  text="{0} is not running!", as_user=True)

            return
    elif command.startswith(commands):
        response = "`do`  Example command; does nothing.\n"
        response += "`commands`  Displays a list of commands and their functions.\n"
        response += "`screencap`  Brings the Miner window to the front, and uploads a screen capture to the channel.\n"
        response += "`start`  *Starts* Miner if it's closed, and starts it mining if it's stopped.\n"
        response += "`stop` *Stops* Miner if it is open / mining.\n"
        response += "`close`  *Closes* Miner\n"
        response += "`shutdown`  *Shutdown* the PC.  *NO WAY TO REMOTE RESTART.*\n"
        response += "`reboot`  *Reboot* the PC."
    elif command.startswith(start):
        start_miner(active_miner_exe)
        response = "{0} started.".format(active_miner_exe.name)
    elif command.startswith(stop):
        running = stop_miner(active_miner_exe)
        response = "{0} not running!".format(active_miner_exe.name)
        if running:
            response = "{0} stopped.".format(active_miner_exe.name)
    elif command.startswith(close):
        running = terminate_miner(active_miner_exe)
        response = "{0} terminated.".format(active_miner_exe.name)
        if not running:
            response = "{0} not running.".format(active_miner_exe.name)
    elif command.startswith(shutdown):
        slack_client.api_call("chat.postMessage", channel=channel,
                              text="Shutting down...", as_user=True)
        shutdown_system()
        return
    elif command.startswith(reboot):
        slack_client.api_call("chat.postMessage", channel=channel,
                              text="Rebooting...", as_user=True)
        reboot_system()
        return

    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


def send_screenshot(active_miner_exe):
    def take_screenshot(date_string, active_miner_exe):
        SetForegroundWindow(find_window(best_match=active_miner_exe.process_name))
        x, y, a, b = pyautogui.locateOnScreen('ir_sample/{0}/header.png'.format(active_miner_exe.dir_name))
        ImageGrab.grab(bbox=(x,
                             y,
                             x - 1 + active_miner_exe.window_width,
                             y + active_miner_exe.window_height)).save("screenshots/{0}.png".format(date_string), "PNG")
    if not miner_exe_running(active_miner_exe.process_name):
        return False
    date = datetime.datetime.now()
    date_string = date.strftime("{0}-{1}-{2}_{3}{4}".format(date.month,
                                                            date.day,
                                                            date.year,
                                                            date.hour,
                                                            date.minute))
    take_screenshot(date_string, active_miner_exe)
    slack_client.api_call('files.upload',
                          channels=channel,
                          filename='{0}.png'.format(date_string),
                          file=open('screenshots/{0}.png'.format(date_string), 'rb'))
    return True


def terminate_miner(active_miner_exe):
    print("Terminating {0} process.".format(active_miner_exe.process_name))
    found = pyautogui.locateOnScreen('ir_sample/{0}/close.png'.format(active_miner_exe.dir_name))
    if found:
        x, y, a, b = found
        pyautogui.click(x + active_miner_exe.exit_offset[0], y + active_miner_exe.exit_offset[1])
        return True
    return False


def stop_miner(active_mining_exe):
    print("searching for stop button...")
    if miner_exe_running(active_miner_exe.process_name):
        found = pyautogui.locateOnScreen('ir_sample/{0}/stop.png'.format(active_miner_exe.dir_name))
        if found:
            x, y, a, b = found
            pyautogui.click(x + active_miner_exe.stop_offset[0], y + active_miner_exe.stop_offset[1])
            return True
    return False


def miner_exe_running(process_name):
    try:
        SetForegroundWindow(find_window(best_match=process_name))
    except MatchError:
        return False
    return True


def start_miner(active_miner_exe):
    def check_for_hardware_warning(active_miner_exe):
        print("searching for hardware warning...")
        found = pyautogui.locateOnScreen('ir_sample/{0}/dismiss.png'.format(active_miner_exe.dir_name))
        if found:
            x, y, a, b = found
            pyautogui.click(x + 20, y + 10)

    def check_for_start_button(active_miner_exe):
        print("searching for start button...")
        print('ir_sample/{0}/start.png'.format(active_miner_exe.dir_name))
        found = pyautogui.locateOnScreen('ir_sample/{0}/start.png'.format(active_miner_exe.dir_name))
        if found:
            print("found the button")
            x, y, a, b = found
            pyautogui.click(x + active_miner_exe.start_offset[0], y + active_miner_exe.start_offset[1])
        else:
            print("did not found the button")

    print(active_miner_exe.process_name)
    print("Starting {0}".format(active_miner_exe.process_name))
    if not miner_exe_running(active_miner_exe.process_name):
        subprocess.Popen(active_miner_exe.process_path)  # this will depend on where you have your mining software installed
        time.sleep(5)  # delay to let miner exe boot, probably overkill, but whatever
    SetForegroundWindow(find_window(best_match=active_miner_exe.process_name))
    if active_mining_exe == "n":
        check_for_hardware_warning()
    check_for_start_button(active_miner_exe)


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
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
