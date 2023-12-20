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
GOOD_STATUSES = ["Accepted"]
BAD_STATUSES = ["Wrong Answer", "Time Limit Exceeded", "Compilation Error", "Runtime Error (SIGSEGV)",
				"Runtime Error (SIGXFSZ)", "Runtime Error (SIGFPE)", "Runtime Error (SIGABRT)", "Runtime Error (NZEC)",
				"Runtime Error (Other)", "Internal Error", "Exec Format Error"]

def main():
	timer = threading.Timer(5.0, check_submissions)
	timer.daemon = True
	timer.start()

@app.post("/create-submission")
async def submit_code(request: Request):
	global current_grader

	data = await request.json()

	if not "code" in data or len(data["code"]) == 0:
		return { "error": "No code provided" }

	if not "testcases" in data:
		return { "error": "No test cases provided" }
	
	if not "language" in data:
		return { "error": "No language provided" }

	to_submit = { "submissions": [] }

	for tc in data["testcases"]:
		to_submit["submissions"].append({
			"language_id": data["language"],
			"source_code": data["code"],
			"expected_output": tc["output"],
			"stdin": tc["input"]
		})

	response = requests.post(GRADER_URLS[current_grader] + "/submissions/batch", json=to_submit)
	response = response.json()
	submission_id = str(uuid.uuid4())
	submission = {
		"testcases": [],
		"status": "In Queue",
		"submitted_time": int(time.time()),
		"percent_accepted": 0,
		"id": submission_id,
		"grader": GRADER_URLS[current_grader]
	}
	current_grader = (current_grader + 1) % len(GRADER_URLS)

	for i in range(len(data["testcases"])):
		if not "token" in response[i]:
			return { "error": "Failed" }
		
		submission["testcases"].append({
			"token": response[i]["token"],
			"status": "In Queue",
			"percent_value": data["testcases"][i]["percent_value"],
			"stderr": ""
		})

	current_submissions[submission_id] = submission
	rolling_submissions.append(submission)

	return { "id": submission_id }

def check_submissions():
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
	
	all_tokens = { k: [] for k in GRADER_URLS }
	token_dict = {}
	for s in current_submissions:
		for tc in current_submissions[s]["testcases"]:
			if tc["status"] in PENDING_STATUSES:
				all_tokens[current_submissions[s]["grader"]].append(tc["token"])
				token_dict[tc["token"]] = { "desc": "In Queue" }

	for grader in all_tokens:
		for index in range(math.ceil(len(all_tokens[grader]) / 10)):
			token_group = all_tokens[grader][index * 10:index * 10 + 10]

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
		percent_accepted = 0
		for i in range(len(sub["testcases"])):
			tc = sub["testcases"][i]
			if tc["token"] in token_dict:
				tc["status"] = token_dict[tc["token"]]["desc"]
				if "stderr" in token_dict[tc["token"]]:
					tc["stderr"] = token_dict[tc["token"]]["stderr"]

			if tc["status"] in PENDING_STATUSES:
				sub["status"] = tc["status"]
				break
			elif tc["status"] in GOOD_STATUSES:
				percent_accepted += tc["percent_value"]
			else:
				sub["status"] = tc["status"] + " on test case " + str(i + 1)
				break
		sub["percent_accepted"] = percent_accepted
		if percent_accepted == 100:
			sub["status"] = "Accepted"

	timer = threading.Timer(5.0, check_submissions)
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
