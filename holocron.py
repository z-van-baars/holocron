import imapclient
import imaplib
from backports import ssl
import pyzmail
import time
from PIL import ImageGrab
import datetime
import smtplib
import os
from pywinauto.findwindows import find_window
from pywinauto.win32functions import SetForegroundWindow

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# email_username = input("Username? ")
# email_password = input("Password? ")
email_username = 'io.holocron'
email_password = 'OPGfPcz62H4T'

imaplib._MAXLINE = 10000000
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
imapObj = imapclient.IMAPClient('imap.gmail.com', ssl=True, ssl_context=context)
imapObj.login(email_username, email_password)
smtpObj = smtplib.SMTP('smtp.gmail.com', 587)
smtpObj.ehlo()
smtpObj.starttls()
smtpObj.login(email_username, email_password)


def check_inbox(imap_object):
    imap_object.select_folder('INBOX', readonly=False)
    UIDs = imapObj.search(['ALL', 'UNSEEN'])
    raw_messages = imap_object.fetch(UIDs, ['BODY[]'])
    return raw_messages, UIDs


def extract_first_line(body_text):
    first_line = ''
    for each_character in body_text:
        if each_character is not "\n":
            first_line += each_character
        else:
            break
    first_line = first_line.strip()
    return first_line


def fetch_address(message):
    gateways = {'@txt.att.net': '@mms.att.net',
                '@mms.att.net': '@mms.att.net',
                '@vzwpix.com': '@vzwpix.com'}

    def return_new_address(address_string, address_suffix):
        def reassign_gateway(address_string):
            gateway = gateways[address_suffix]
            return gateway

        address_suffix = reassign_gateway(address_suffix)
        return_number = address_string[:10]
        address_string = return_number + address_suffix
        return address_string

    address_string = message.get_addresses('from')[0][1]
    for each_character in address_string:
        if each_character is '@':
            address_suffix = address_string[address_string.index('@'):]
            print(address_suffix)
            break
    if address_suffix in gateways:
        address_string = return_new_address(address_string, address_suffix)
    return address_string


def send_screenshot(message):
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
    msg_text = "Here's that screenshot."
    msg = MIMEMultipart()
    msg.attach(MIMEText(msg_text, 'plain'))
    image_data = open('screenshots/{0}.png'.format(date_string), 'rb').read()
    image = MIMEImage(image_data, name=os.path.basename('screenshots/{0}.png'.format(date_string)))
    msg.attach(image)
    address_string = fetch_address(message)
    smtpObj.sendmail('Sheev', address_string, msg.as_string())


def command_parsing(message, message_string):
    if message_string.lower() == "screencap":
        send_screenshot(message)


def main():
    while True:
        new_messages, UIDs = check_inbox(imapObj)
        for eachID in UIDs:
            message = pyzmail.PyzMessage.factory(new_messages[eachID][b'BODY[]'])
            assert message.text_part is not None
            body_text = message.text_part.get_payload().decode(message.text_part.charset)
            message_string = extract_first_line(body_text)
            command_parsing(message, message_string)

        time.sleep(30)


main()


imapObj.logout()
