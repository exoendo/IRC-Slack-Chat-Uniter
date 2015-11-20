#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import json
import socket
import settings
import threading
import HTMLParser
from slackclient import SlackClient


class uniter(object):

    def __init__(self, server, channel, nick, password):
        time.sleep(60)  # In event of heroku SIGTERM,
                        # we wait so IRC fully disconnects our name
        self.channel = channel
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((server, 6667))
        self.ignore_list = ['gonzobot', 'lazybot', 'redditBot']

        time.sleep(5)

        self.s.send('USER {0} {1} {2}:{3}\n'.format(
            nick, nick, nick, 'Mr. Bot'))

        self.s.send('NICK {}\n'.format(nick))

        while True:
            time.sleep(.5)
            text = self.s.recv(1024)

            if text.find(':End of message of the day.') != -1:
                self.s.send('PRIVMSG nickserv :IDENTIFY {}\n'.format(
                    password))
                time.sleep(5)  # Give time for server to authenticate
                self.s.send('JOIN {}\n'.format(self.channel))
                print '\n--> Connected on IRC'
                break
            else:
                pass
            print text
            if text.find('PING :') != -1:
                self.s.send('PONG :{}\n'.format(text.split('PING :')[1]))

    def slack_connect(self, token):
        ''' Connects to Slack '''

        self.sc = SlackClient(token)
        self.d = {}

        try:
            self.sc.rtm_connect()
            print '--> Slack connection Successful'
        except Exception as e:
            print str(e)
            exit()

        # the chat stream does not provide usernames with messages,
        # only ID's. So we are building a dictionary of all corresponding
        # IDs and matching them with their usernames, to refer to later
        json_data = self.sc.api_call("users.list")
        parse = json.loads(json_data)

        for info in parse['members']:  # maps slack ID's to usernames
            self.d[info['id']] = info['name']

    def irc_parse(self, text_stream):
        ''' Get IRC data and send it to Slack '''

        username = re.findall(r':(.*?)!', text_stream)[0]
        if str(username) in self.ignore_list:
            pass
        else:
            username = u'{}\u200B{}'.format(username[0], username[1:])
            username = username.encode('utf-8', 'ignore')
            body = text_stream.split('{} :'.format(self.channel))[1]
            message = '<{}> {}'.format(username, body)

            self.sc.api_call('chat.postMessage',
                             channel='C039KQ6EK', text=message)

    def slack_parse(self, data):
        ''' Take Slack data and send to IRC '''

        user_id = data[0]['user']
        user_s = self.d[user_id]

        if str(user_s) in self.ignore_list:
            return
        else:
            slack_username = u'{}\u200B{}'.format(user_s[0], user_s[1:])
            slack_username = slack_username.encode('utf-8', 'ignore')

            # Slack has lots of odd chars, encode body to unicode
            slack_body = data[0]['text'].encode('utf-8')

            # Parses < and > brackets:
            if '&lt;' in slack_body or '&gt;' in slack_body:
                h = HTMLParser.HTMLParser()
                slack_body = h.unescape(slack_body)

            slack_message = '\x02<{}>\x0F {}'.format(slack_username,
                                                      slack_body)
            self.s.send('PRIVMSG {} :{}\n'.format(self.channel,
                                                  slack_message))

    def irc_run(self):
        ''' Main IRC loop '''

        print '--> IRC loop is running..'
        time.sleep(5)
        while True:
            try:
                time.sleep(.5)
                text = self.s.recv(1024)
                print text

                if text.find('PING :') != -1:  # func returns -1 if no match
                    self.s.send('PONG :{}\n'.format(text.split('PING :')[1]))
                    print 'PONG :{}'.format(text.split('PING :')[1])

                elif re.search('PRIVMSG {}'.format(self.channel), text):
                    self.irc_parse(text)

            except Exception as e:
                print str(e)

    def slack_run(self):
        ''' Main Slack loop '''

        print '--> Slack loop is running..\n'
        time.sleep(10)  # So we don't get irc TOPIC and stuff printing out
        while True:
            try:
                data = self.sc.rtm_read()
                if not data:
                    continue
                elif data[0]['type'] != 'message':
                    continue
                elif 'text' not in data[0]:
                    continue
                elif 'user' not in data[0]:
                    continue
                elif data[0]['user'] == 'U0D54GKM5':  # If user = IRCbot
                    continue
                else:
                    self.slack_parse(data)
            except Exception as e:
                print str(e)

if __name__ == '__main__':

        chat = uniter(settings.server,
                      settings.channel,
                      settings.nick,
                      settings.password)

        chat.slack_connect(settings.Slack_token)

        t1 = threading.Thread(target=chat.irc_run)
        t1.start()
        t2 = threading.Thread(target=chat.slack_run)
        t2.start()
