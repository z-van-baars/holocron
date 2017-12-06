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

        if send_screenshot():
            slack_client.api_call("chat.postMessage", channel=channel,
                                  text="Here's that screencap.", as_user=True)
            return
        else:
            slack_client.api_call("chat.postMessage", channel=channel,
                                  text="NiceHash Miner is not running!", as_user=True)

            return
    elif command.startswith(commands):
        response = "`do`  Example command; does nothing.\n"
        response += "`commands`  Displays a list of commands and their functions.\n"
        response += "`screencap`  Brings the NiceHash Miner window to the front, and uploads a screen capture to the channel.\n"
        response += "`start`  *Starts* NiceHash Miner if it's closed, and starts it mining if it's stopped.\n"
        response += "`stop` *Stops* NiceHash Miner if it is open / mining.\n"
        response += "`close`  *Closes* NiceHash Miner\n"
        response += "`shutdown`  *Shutdown* the PC.  *NO WAY TO REMOTE RESTART.*\n"
        response += "`reboot`  *Reboot* the PC."
    elif command.startswith(start):
        start_nicehash()
        response = "NiceHash Miner started."
    elif command.startswith(stop):
        running = stop_nicehash()
        response = "NiceHash Miner not running!"
        if running:
            response = "NiceHash Miner stopped."
    elif command.startswith(close):
        running = terminate_nicehash()
        response = "NiceHash Miner terminated."
        if not running:
            response = "NiceHash Miner not running."
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


def send_screenshot():
    def take_screenshot(date_string):
        SetForegroundWindow(find_window(best_match='NiceHash'))
        x, y, a, b = pyautogui.locateOnScreen('ir_sample/nicehash_header.png')
        ImageGrab.grab(bbox=(x - 1, y, x - 1 + NH_WINDOW_W, y + NH_WINDOW_H)).save("screenshots/{0}.png".format(date_string), "PNG")
    if not nicehash_exe_running():
        return False
    date = datetime.datetime.now()
    date_string = date.strftime("{0}-{1}-{2}_{3}{4}".format(date.month,
                                                            date.day,
                                                            date.year,
                                                            date.hour,
                                                            date.minute))
    take_screenshot(date_string)
    slack_client.api_call('files.upload',
                          channels=channel,
                          filename='{0}.png'.format(date_string),
                          file=open('screenshots/{0}.png'.format(date_string), 'rb'))
    return True


def checkin():
    checkin_greeting = at_bot + "online!"
    slack_client.api_call("chat.postMessage", channel=DEFAULT_CHANNEL,
                          text=checkin_greeting, as_user=True)


def terminate_nicehash():
    print("Terminating NiceHash process.")
    found = pyautogui.locateOnScreen('ir_sample/close.png')
    if found:
        x, y, a, b = found
        pyautogui.click(x + 62, y + 27)
        return True
    return False


def stop_nicehash():
    print("searching for stop button...")
    if nicehash_exe_running():
        found = pyautogui.locateOnScreen('ir_sample/stop.png')
        if found:
            x, y, a, b = found
            pyautogui.click(x + 30, y - 60)
            return True
    return False


def nicehash_exe_running():
    try:
        SetForegroundWindow(find_window(best_match='NiceHash'))
    except MatchError:
        return False
    return True


def start_nicehash():
    def check_for_hardware_warning():
        print("searching for hardware warning...")
        found = pyautogui.locateOnScreen('ir_sample/dismiss.png')
        if found:
            x, y, a, b = found
            pyautogui.click(x + 20, y + 10)

    def check_for_start_button():
        print("searching for start button...")
        found = pyautogui.locateOnScreen('ir_sample/start.png')
        if found:
            x, y, a, b = found
            pyautogui.click(x + 36, y + 36)

    print("Starting NiceHash miner 2 exe.")
    if not nicehash_exe_running():
        subprocess.Popen(lines[5])  # this will depend on where you have nhm installed
        time.sleep(60)  # delay to let nicehash miner 2 boot up, probably overkill, but whatever
    check_for_hardware_warning()
    check_for_start_button()


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
