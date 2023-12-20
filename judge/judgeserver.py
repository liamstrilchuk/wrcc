from fastapi import Request, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests, uuid, time, threading, math

GRADER_URLS = ["http://localhost:2358"]
current_grader = 0
current_submissions = {}
rolling_submissions = []
app = FastAPI()
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)
PENDING_STATUSES = ["In Queue", "Processing"]
NOT_RUN_STATUSES = ["Not Run"]
GOOD_STATUSES    = ["Accepted"]
BAD_STATUSES     = ["Wrong Answer", "Time Limit Exceeded", "Compilation Error", "Runtime Error (SIGSEGV)",
					"Runtime Error (SIGXFSZ)", "Runtime Error (SIGFPE)", "Runtime Error (SIGABRT)", "Runtime Error (NZEC)",
					"Runtime Error (Other)", "Internal Error", "Exec Format Error"]

def main():
	timer = threading.Timer(5.0, check_submissions)
	timer.daemon = True
	timer.start()

@app.post("/create-submission")
async def submit_code(request: Request):
	data = await request.json()

	if not "code" in data or len(data["code"]) == 0:
		return { "error": "No code provided" }

	if not "testcases" in data or len(data["testcases"]) == 0:
		return { "error": "No test cases provided" }

	if not "language" in data:
		return { "error": "No language provided" }

	tctoken, tcgrader = submit_testcase(data["testcases"][0], data["language"], data["code"])

	submission_id = str(uuid.uuid4())
	submission = {
		"testcases": [],
		"status": "In Queue",
		"submitted_time": int(time.time()),
		"percent_accepted": 0,
		"id": submission_id,
		"code": data["code"],
		"language": data["language"],
		"finished": False
	}

	for tc in data["testcases"]:
		submission["testcases"].append({
			"token": "",
			"grader": "",
			"status": "Not Run",
			"percent_value": tc["percent_value"],
			"input": tc["input"],
			"output": tc["output"],
			"stderr": ""
		})

	submission["testcases"][0]["token"] = tctoken
	submission["testcases"][0]["grader"] = tcgrader
	submission["testcases"][0]["status"] = "In Queue"

	current_submissions[submission_id] = submission
	rolling_submissions.append(submission)

	return { "id": submission_id }

def submit_testcase(tc, language, code):
	global current_grader

	to_submit = { "submissions": [] }

	to_submit["submissions"].append({
		"language_id": language,
		"source_code": code,
		"expected_output": tc["output"],
		"stdin": tc["input"]
	})

	response = requests.post(GRADER_URLS[current_grader] + "/submissions/batch", json=to_submit)
	response = response.json()

	token = response[0]["token"]
	grader = GRADER_URLS[current_grader]
	current_grader = (current_grader + 1) % len(GRADER_URLS)

	return token, grader

def check_submissions():
	try:
		for s in rolling_submissions:
			if time.time() > s["submitted_time"] + 600:
				rolling_submissions.remove(s)

		for s in [*current_submissions.keys()]:
			if time.time() > current_submissions[s]["submitted_time"] + 1200:
				del current_submissions[s]

		if len(current_submissions) == 0:
			timer = threading.Timer(5.0, check_submissions)
			timer.daemon = True
			timer.start()
			return

		all_tokens = []
		token_dict = {}
		for s in current_submissions:
			for tc in current_submissions[s]["testcases"]:
				if tc["status"] in PENDING_STATUSES:
					all_tokens.append(tc["token"])
					token_dict[tc["token"]] = { "desc": "In Queue" }

		for grader in GRADER_URLS:
			for index in range(math.ceil(len(all_tokens) / 20)):
				token_group = all_tokens[index * 20:index * 20 + 20]

				response = requests.get(grader + "/submissions/batch?fields=stdout,time,memory,stderr,token,compile_output,message,status&base64_encoded=true&tokens=" + ",".join(token_group))
				response = response.json()

				for tc in response["submissions"]:
					if tc is None:
						continue

					token_dict[tc["token"]] = { "desc": tc["status"]["description"] }
					if "stderr" in tc:
						token_dict[tc["token"]]["stderr"] = tc["stderr"]

		for s in current_submissions:
			sub = current_submissions[s]
			if sub["finished"]:
				continue
			percent_accepted = 0
			for i in range(len(sub["testcases"])):
				tc = sub["testcases"][i]
				if tc["token"] in token_dict:
					tc["status"] = token_dict[tc["token"]]["desc"]
					if "stderr" in token_dict[tc["token"]]:
						tc["stderr"] = token_dict[tc["token"]]["stderr"]

				if tc["status"] in NOT_RUN_STATUSES:
					token, grader = submit_testcase(tc, sub["language"], sub["code"])
					tc["token"] = token
					tc["status"] = "In Queue"
					tc["grader"] = grader
					break
				elif tc["status"] in PENDING_STATUSES:
					sub["status"] = tc["status"]
					break
				elif tc["status"] in GOOD_STATUSES:
					percent_accepted += tc["percent_value"]
				else:
					sub["finished"] = True
					sub["status"] = tc["status"] + " on test case " + str(i + 1)
					break
			sub["percent_accepted"] = percent_accepted
			if percent_accepted == 100:
				sub["status"] = "Accepted"
	except:
		pass

	timer = threading.Timer(2.0, check_submissions)
	timer.daemon = True
	timer.start()

@app.post("/submissions")
async def get_submissions(request: Request):
	data = await request.json()
	to_respond = {}
	to_delete = []

	for s in current_submissions:
		if s in data["submissions"]:
			to_respond[s] = {
				"status": current_submissions[s]["status"],
				"percent_accepted": current_submissions[s]["percent_accepted"]
			}

		if current_submissions[s]["status"] not in PENDING_STATUSES and data["autodelete"]:
			to_delete.append(s)

	for s in to_delete:
		del current_submissions[s]

	return { "submissions": to_respond }

@app.get("/current")
async def get_current_submissions():
	return rolling_submissions

main()