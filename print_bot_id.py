from slackclient import SlackClient

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

bot_name = lines[0]

slack_client = SlackClient(lines[2])


if __name__ == "__main__":
    api_call = slack_client.api_call("users.list")
    if api_call.get('ok'):
        # retrieve all users so we can find our bot
        users = api_call.get('members')
        for user in users:
            if 'name' in user and user.get('name') == bot_name:
                print("Bot ID for '" + user['name'] + "' is " + user.get('id'))
    else:
        print("could not find bot user with the name " + bot_name)
