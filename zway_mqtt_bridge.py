import os
import json
import sys
import urllib2
import time

import mosquitto
client = None
url = 'http://localhost:8083/ZWaveAPI'

#~ def pub(topic, val):
	#~ print "pub", topic, " <= ", val



def mqtt_escape(s):
	return s.replace('/','_').replace(' ','_')

def mqtt_publish_device(dev_id, device_name):
	topic = "/devices/%s" % dev_id
	if device_name:
		client.publish(topic + "/meta/name", str(device_name))
	client.publish(topic + "/meta/room", "z-wave")


def mqtt_publish_control(dev_id, control_id, value, meta={}):
	topic = "/devices/%s/controls/%s" % (dev_id, control_id)

	client.publish(topic, value, retain=True)
	for key, meta_value in meta.iteritems():
		client.publish(topic + "/meta/" + key, meta_value, retain=True)



def on_mqtt_message(arg0, arg1, arg2=None):
    #
    #~ print "on_mqtt_message", arg0, arg1, arg2
	if arg2 is None:
		mosq, obj, msg = None, arg0, arg1
	else:
		mosq, obj, msg = arg0, arg1, arg2
	print msg.topic

	parts = msg.topic.split('/')

	mqtt_dev_id = parts[2]
	mqtt_control_id = parts[4]

	dev_id = mqtt_dev_id.split('_', 1)

	control_parts = mqtt_control_id.split('_', 2)
	if len(control_parts) < 2:
		return

	inst_id, class_id = control_parts[:2]


	if msg.payload == '1':
		val = '255'
	else:
		val = '0'

	cmd_url = urllib2.quote("/Run/devices[%s].instances[%s].commandClasses[%s].Set(%s)" %  (dev_id, inst_id, class_id, val))
	urllib2.urlopen(url + cmd_url, '').read()





subscribed_topics=set()

def ensure_subscribe_control(dev_id, control_id):
	topic = str('/devices/%s/controls/%s/on' % (dev_id, control_id))
	if topic not in subscribed_topics:
	    client.subscribe(topic)
	else:
		subscribed_topics.add(topic)



def process_data(url):

	data = urllib2.urlopen(url).read()
	obj = json.loads(data)
	#~ print obj

	# class 156 => AlarmSensor
	# class 48 => SensorBinary
	#  class 37 SwitchBinary
	#~ 49 SensorMultilevel


	for dev_id in obj["devices"].keys():
			if not dev_id.isdigit():
				continue


			dev_name = obj["devices"][dev_id]["data"]["givenName"]["value"]
			mqtt_dev_id = "%s_%s" % (dev_id, mqtt_escape(dev_name))


			print "====", dev_name, dev_id
			#~ obj["devices"][dev_id]["data"]["givenName"]["value"]

			mqtt_publish_device(mqtt_dev_id	, dev_name)

			for inst_id in obj["devices"][dev_id]["instances"]:
				if not inst_id.isdigit():
					continue
				#~ print "inst_id: ", inst_id

				#~ print obj["devices"][dev_id]["instances"][inst_id]["commandClasses"].keys()

				for class_id  in obj["devices"][dev_id]["instances"][inst_id]["commandClasses"]:
					if not class_id.isdigit():
						continue

					#~ print "class:", class_id

					if class_id == '37':
						value = obj["devices"][dev_id]["instances"][inst_id]["commandClasses"][class_id]["data"]["level"]["value"]

						if value is not None:
							control_id = "%s_%s" % (inst_id, class_id)
							mqtt_publish_control(mqtt_dev_id, control_id, int(value), {'type' : 'switch'})
							ensure_subscribe_control(mqtt_dev_id, control_id)






					for sensor_id in obj["devices"][dev_id]["instances"][inst_id]["commandClasses"][class_id]["data"]:
						if not sensor_id.isdigit():
							continue

						sens_obj = obj["devices"][dev_id]["instances"][inst_id]["commandClasses"][class_id]["data"][sensor_id]
						#~ print sens_obj

						if 'sensorTypeString' in sens_obj:
							sens_name = sens_obj["sensorTypeString"]["value"]
						else:
							sens_name = None

						mqtt_control_id = "%s_%s_%s_%s" % (inst_id, class_id, sensor_id, mqtt_escape(sens_name) if sens_name else 'none')
						if class_id in ("48", ):
							print "sens:", sens_name
							print "sens val:", sens_obj["level"]["value"]

							mqtt_publish_control(mqtt_dev_id, mqtt_control_id, int(sens_obj["level"]["value"]), {'type' : 'switch', 'readonly': '1'})
						elif class_id == '49':
							#fixme proper types
							val_str = str(sens_obj["val"]["value"]) + ' ' + sens_obj["scaleString"]["value"]
							val_str = val_str.encode('utf8', 'ignore')
							mqtt_publish_control(mqtt_dev_id, mqtt_control_id, val_str, {'type' : 'text'})




if __name__ == '__main__':

	client = mosquitto.Mosquitto()
	client.connect('localhost')
	client.on_message = on_mqtt_message


	client.loop_start()



	while True:
		process_data(url + "/Data/0")
		time.sleep(1)

