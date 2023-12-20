import json, time


def add_to_log(event_type, event_desc):
	log = load_log()
	if len(log) == 100:
		log = log[:-1]
	log.insert(0, {
		"time": int(time.time()),
		"type": event_type,
		"desc": event_desc
	})

	with open("adminlog.json", "w") as f:
		f.write(json.dumps(log, indent="\t"))


def load_log():
	return json.loads(open("adminlog.json", "r").read())
