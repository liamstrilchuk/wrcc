import json, os

def load_contest_data():
	contests = os.listdir("contests")
	contest_data = {}

	for contest in contests:
		with open(f"contests/{contest}/contest.json", "r") as f:
			contest_data[contest] = json.load(f)

		contest_data[contest]["question_data"] = []

		for question in contest_data[contest]["questions"]:
			with open(f"contests/{contest}/questions/{question}/question.json", "r") as f:
				contest_data[contest]["question_data"].append(json.load(f))
				contest_data[contest]["question_data"][-1]["id"] = question

		for question in contest_data[contest]["question_data"]:
			question["test_case_data"] = []
			for item in question["test_cases"]:
				question["test_case_data"].append({
					"percent_value": item["percent_value"]
				})
				with open(f"contests/{contest}/questions/{question['id']}/{item['input']}", "r") as f:
					question["test_case_data"][-1]["input"] = f.read()

				with open(f"contests/{contest}/questions/{question['id']}/{item['output']}", "r") as f:
					question["test_case_data"][-1]["output"] = f.read()

	return contest_data
