#!/usr/bin/env python

import sys
import time
import json
import signal
import logging
import argparse
import paho.mqtt.client as mqtt
from mitsi import *


class Handler(object):
    def __init__(self, serial_port, broker, prefix, user=None, password=None):
        self.running = True
        self.prefix = prefix
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)

        self.broker = broker
        self.client = mqtt.Client(protocol=mqtt.MQTTv31)
        if user:
            self.client.username_pw_set(user, password)
        will_topic = 'connected'
        if prefix:
            will_topic = '%s/%s' % (prefix, will_topic)
        self.client.will_set(will_topic, '0', qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        #self.client.on_subscribe = self.on_subscribe
        log.info('Connecting to MQTT broker: %s', self.broker)
        self.client.connect(broker)
        self.publish('connected', 1, qos=1, retain=True)
        self.connected_state = 1
        self.timeToSend = 60

        self.hp = HeatPump(serial_port)
        self.hp.connect()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.client.subscribe('%s/command/#' % self.prefix)
            log.info('Connected to MQTT broker (code=%s)', rc)
        else:
            log.info('Failed to connect to MQTT broker(code=%s)', rc)

    #def on_subscribe(self, client, mid, granted_qos, somethingelse):
        #log.info(granted_qos)

    def publish(self, topic, payload, **kwargs):
        topic = '%s/%s' % (self.prefix, topic)
        self.client.publish(topic, payload, **kwargs)
 
    def run(self):
        while self.running:
            self.hp.loop()
            if (self.hp.valid and self.hp.dirty) or self.timeToSend < 0:
                if self.connected_state != 2:
                    self.publish('connected', 2, qos=1, retain=True)
                    self.connected_state = 2
                # log.debug('MQTT: Publishing status to /state topic')
                self.publish('state', json.dumps(self.hp.to_dict()), retain=True)
                log.info("MQTT TX : %s : %s" % ('state', json.dumps(self.hp.to_dict())))
                self.hp.dirty = False
                self.timeToSend = 60
            if self.client.loop() != 0:
                log.warning('Disonnected from MQTT broker: %s', self.broker)
                try:
                    self.client.connect(self.broker)
                except:
                    time.sleep(1)
            self.timeToSend = self.timeToSend - 1

    def on_message(self, client, userdata, msg):
        log.debug('MQTT RX : %s : %s' % (msg.topic, msg.payload))
        topic = msg.topic
        if self.prefix:
            topic = topic.partition('%s/' % self.prefix)[2]
        msg_type, s, topic = topic.partition('/')
        if msg_type == 'command':
            if topic == 'set':
                try:
                    state = json.loads(msg.payload)
                except ValueError:
                    log.warning('Invalid JSON: %s' % msg.payload)
                self.hp.set(state)
            if topic == 'status':
                self.timeToSend = 0

    def cleanup(self, signum, frame):
        self.running = False
        self.client.disconnect()
        sys.exit(signum)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bridge Mitsi and MQTT')
    parser.add_argument('--mqtt-host',
                        default='localhost', help='MQTT broker')
#    parser.add_argument('--mqtt-port',
#                        default='1883', type=int, help='MQTT port')
    parser.add_argument('--mqtt-prefix',
                        default='mqmitsi',
                        help='MQTT topic prefix prepended to messages')
    parser.add_argument('--serial-port',
                        default='/dev/ttyAMA0',
                        help='Serial device to communicate on')
    parser.add_argument('--log',
                        help='Set log level. Defaults to WARNING')
    args = parser.parse_args()

    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)-15s %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    console.setLevel(logging.DEBUG)
    log.addHandler(console)
    if args.log:
        console.setLevel(args.log)

    h = Handler(args.serial_port, broker=args.mqtt_host, prefix=args.mqtt_prefix)
    h.run()
