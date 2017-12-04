import os
import time
from slackclient import SlackClient
from pywinauto.findwindows import find_window
from pywinauto.win32functions import SetForegroundWindow
from PIL import ImageGrab
import datetime

bot_id = 'BOT ID GOES HERE'
slack_client = SlackClient(API TOKEN GOES HERE)

at_bot = '@' + bot_id
example_command = "do"
screencap = "screencap"


def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = "Not sure what you mean. Use the *" + example_command + "* command with numbers, delimited by spaces."
    print(command)
    if command.startswith(example_command):
        response = "Sure...write some more code then I can do that!"
    elif command.startswith(screencap):
        response = "Here's that screencap you wanted."

    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


def send_screenshot():
    def take_screenshot(date_string):
        SetForegroundWindow(find_window(best_match='NiceHash'))
        ImageGrab.grab().save("screenshots/{0}.png".format(date_string), "PNG")

    date = datetime.datetime.now()
    date_string = date.strftime("{0}-{1}-{2}_{3}{4}".format(date.month,
                                                            date.day,
                                                            date.year,
                                                            date.hour,
                                                            date.minute))
    take_screenshot(date_string)



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
                # return text after the @ mention, whitespace removed
                return ((output['text'].split(at_bot)[1]).strip()).lower(), output['channel']
    return None, None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
