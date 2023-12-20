from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request
)
from flask_login import (
	login_user,
	LoginManager,
	current_user,
	logout_user,
	login_required
)
from flask_wtf import CSRFProtect
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from models import User, Team, Contest, Submission, db
from load_contests import load_contest_data
from adminlog import add_to_log, load_log
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import util, time, requests, threading, os, json, atexit

GRADER_URL = "http://localhost:6000"
current_submissions = []
rate_limits = []
process_log = "logs/" + util.random_string(10) + ".json"

login_manager = LoginManager()
login_manager.login_view = "get_login"
login_manager.session_protection = "strong"

migrate = Migrate()
bcrypt = Bcrypt()
contest_data = load_contest_data()
csrf = None

ACCEPTED_EXTENSIONS = ["py", "cpp", "java", "c", "js"]
LANGUAGE_IDS = {
	"cpp": 54,
	"c": 50,
	"java": 62,
	"javascript": 63,
	"py": 71
}
ADMIN_TOKEN = open("admintoken.txt", "r").read()

def check_submissions():
	with app.app_context():
		global current_submissions
		if len(current_submissions) == 0:
			timer = threading.Timer(5.0, check_submissions)
			timer.daemon = True
			timer.start()
			return

		tokens = []
		for submission in current_submissions:
			tokens.append(submission[1])

		response = requests.post(GRADER_URL + "/submissions", json={
			"submissions": tokens,
			"autodelete": False
		})
		data = response.json()

		with open(process_log, "w") as f:
			f.write(json.dumps({ "last_data": data, "current_submissions": current_submissions }))

		to_remove = []
		for submission in current_submissions:
			submission_item = db.session.query(Submission).filter_by(id=submission[0]).first()
			if submission[1] in data["submissions"]:
				sdata = data["submissions"][submission[1]]
				submission_item.status = "Processing" if sdata["status"] in ["In Queue", "Processing"] else "Completed"
				submission_item.verdict = sdata["status"].lower().capitalize()
				submission_item.percent_earned = sdata["percent_accepted"]

				if sdata["status"] not in ["In Queue", "Processing"]:
					to_remove.append(submission)
		
		for i in to_remove:
			current_submissions.remove(i)
		
		db.session.commit()
		timer = threading.Timer(5.0, check_submissions)
		timer.daemon = True
		timer.start()

def create_app():
	global csrf
	app = Flask(__name__)
	app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
	app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
	app.secret_key = os.environ["SECRET_KEY"]

	app.jinja_env.auto_reload = True
	app.config["TEMPLATES_AUTO_RELOAD"] = True

	db.init_app(app)
	migrate.init_app(app, db)
	bcrypt.init_app(app)
	csrf = CSRFProtect(app)
	login_manager.init_app(app)
	timer = threading.Timer(5.0, check_submissions)
	timer.daemon = True
	timer.start()

	return app

app = create_app()

def clear_request_data():
	files = os.listdir("request_data")

	for f in files:
		date = datetime(int(f[0:4]), int(f[4:6]), int(f[6:8]), int(f[8:10]), int(f[10:12]))
		if (datetime.now() - date).seconds > 3600:
			os.remove("request_data/" + f)

request_data_scheduler = BackgroundScheduler()
request_data_scheduler.add_job(func=clear_request_data, trigger="interval", seconds=60)
request_data_scheduler.start()

atexit.register(lambda: request_data_scheduler.shutdown())

@app.before_request
def before_request():
	try:
		now = datetime.now()
		current_min = "".join(str(i if len(str(i)) >= 2 else "0" + str(i)) for i in [now.year, now.month, now.day, now.hour, now.minute])
		data = { "total": 0 }
		file_name = f"request_data/{current_min}.json"

		if os.path.isfile(file_name):
			data = json.loads(open(file_name, "r").read())

		user_name = current_user.username if current_user.is_authenticated else "unregistered"
		if not user_name in data:
			data[user_name] = 0

		data[user_name] += 1
		data["total"] += 1

		with open(file_name, "w") as f:
			f.write(json.dumps(data))

		if data[user_name] > 200 and current_user.is_authenticated and not current_user.is_admin:
			return render_template("ratelimited.html")
	except Exception as e:
		print(e)

@app.route("/login", methods=["GET"])
def get_login():
	return render_template("login.html")

@app.route("/login", methods=["POST"])
def post_login():
	username = request.form.get("username")
	password = request.form.get("password")

	if not username or not password:
		return redirect(url_for("get_login"))

	user = User.query.filter_by(username=username.lower()).first()

	if user and bcrypt.check_password_hash(user.password, password):
		login_user(user)
		add_to_log("Login", username)
		return redirect(url_for("index"))

	return redirect(url_for("get_login"))

@app.route("/logout")
@login_required
def logout():
	add_to_log("Logout", current_user.username)
	logout_user()
	return redirect(url_for("get_login"))

@app.route("/")
@login_required
def index():
	return render_template("index.html")

@app.route("/adminlog")
@login_required
def getadminlog():
	if not current_user.is_admin:
		return redirect("/")

	log = load_log()
	return render_template("adminlog.html", log=log)

@app.route("/api/contests")
@login_required
def api_contests():
	contests = load_contests()
	sterilized_contests = []
	for item in contests:
		sterilized_contests.append({
			"name": item.name,
			"short_name": item.short_name,
			"individual": item.individual,
			"start_date": item.start_date,
			"end_date": item.end_date
		})
	return { "contests": sterilized_contests }

@app.route("/api/contest/<contest_name>")
@login_required
def api_contest(contest_name):
	metadata = get_contest_metadata(contest_name)
	
	if metadata is None:
		return { "error": "Contest not found" }

	if metadata.start_date > time.time() and not current_user.is_admin:
		return { "error": "Contest not started" }

	contest = contest_data[contest_name]
	sterilized_contest = {
		"name": metadata.name,
		"individual": metadata.individual,
		"start_date": metadata.start_date,
		"end_date": metadata.end_date,
		"questions": []
	}
	if metadata.individual or not current_user.team:
		accepted_submissions = Submission.query.filter_by(
			user_id=current_user.id,
			contest_name=contest_name
		)
	else:
		accepted_submissions = Submission.query.filter_by(
			team_id=current_user.team,
			contest_name=contest_name
		)
	for question in contest["question_data"]:
		sterilized_contest["questions"].append({
			"id": question["id"],
			"name": question["name"],
			"content": question["content"],
			"input": question["input"],
			"output": question["output"],
			"short_name": question["short_name"],
			"point_value": question["point_value"],
			"percent_earned": 0
		})
	for item in accepted_submissions:
		for question in sterilized_contest["questions"]:
			if question["short_name"] == item.question and item.percent_earned > question["percent_earned"]:
				question["percent_earned"] = item.percent_earned

	return { "contest": sterilized_contest }

@app.route("/api/submissions/<contest_name>")
def api_submissions(contest_name):
	metadata = get_contest_metadata(contest_name)
	
	if metadata is None:
		return { "error": "Contest not found" }
	
	contest = Contest.query.filter_by(short_name=contest_name).first()
	if contest.individual or not current_user.team:
		submissions = current_user.submissions
	else:
		submissions = Submission.query.filter_by(team_id=current_user.team).all()
	sterilized_submissions = []
	for item in submissions:
		if item.contest_name == contest.short_name:
			sterilized_submissions.append({
				"question": item.question,
				"filename": item.filename,
				"language": item.language,
				"timestamp": item.timestamp,
				"status": item.status,
				"verdict": item.verdict,
				"id": item.id,
				"percent_earned": item.percent_earned
			})
	sterilized_submissions.reverse()
	return { "submissions": sterilized_submissions }

@app.route("/api/dashboard/<contest_name>")
@login_required
def api_dashboard(contest_name):
	if not current_user.is_admin:
		return { "error": "Not authorized" }
	
	metadata = get_contest_metadata(contest_name)
	if metadata is None:
		return { "error": "Contest not found" }
	
	contest = Contest.query.filter_by(short_name=contest_name).first()
	questions = []
	if contest.individual:
		all_users = User.query.all()
		user_questions = { user.username: [] for user in all_users }
	else:
		all_teams = Team.query.all()
		user_questions = { team.name: [] for team in all_teams }

	for question in contest_data[contest_name]["question_data"]:
		questions.append({
			"name": question["name"],
			"short_name": question["short_name"],
			"point_value": question["point_value"]
		})
		if contest.individual:
			for user in all_users:
				submission = Submission.query.filter_by(
					user_id=user.id,
					contest_name=contest.short_name,
					question=question["short_name"]
				).order_by(Submission.percent_earned.desc()).first()

				if submission is None:
					user_questions[user.username].append([0, False])
					continue

				user_questions[user.username].append([submission.percent_earned, True])
		else:
			for team in all_teams:
				submission = Submission.query.filter_by(
					team_id=team.id,
					contest_name=contest.short_name,
					question=question["short_name"]
				).order_by(Submission.percent_earned.desc()).first()

				if submission is None:
					user_questions[team.name].append([0, False])
					continue

				user_questions[team.name].append([submission.percent_earned, True])

	return {
		"questions": questions,
		"user_questions": user_questions,
		"individual": contest.individual
	}

@app.route("/api/submission/<submission_id>")
@login_required
def api_submission(submission_id):
	submission = Submission.query.filter_by(id=submission_id).first()
	if submission is None:
		return { "error": "Submission not found" }
	
	if not submission.user_id == current_user.id and not current_user.is_admin:
		return { "error": "Not authorized" }
	
	if not os.path.exists(submission.filename):
		return { "error": "File not found" }
	
	with open(submission.filename, "r") as f:
		code = f.read()
	
	return {
		"question": submission.question,
		"filename": submission.filename,
		"language": submission.language,
		"timestamp": submission.timestamp,
		"status": submission.status,
		"verdict": submission.verdict,
		"code": code
	}

@app.route("/create-user", methods=["GET"])
@login_required
def create_user_page():
	if not current_user.is_admin:
		return redirect("/")

	return render_template("createuser.html")

@app.route("/create-user", methods=["POST"])
@login_required
def create_user_post():
	if not current_user.is_admin:
		return redirect("/")

	username = request.form.get("username")
	password = request.form.get("password")
	is_admin = request.form.get("is_admin")

	if not username or not password:
		return redirect("/create-user")
	
	is_admin = is_admin == "on"

	add_to_log("User created", username + " was created by " + current_user.username)
	create_user(username, password, "", "", is_admin)
	return redirect("/manage")

@app.route("/create-user-api", methods=["GET"])
def create_user_api():
	if not request.args.get("token", default="") == ADMIN_TOKEN:
		return redirect("/login")
	
	username = request.args.get("username")
	password = request.args.get("password")

	if not username or not password:
		return redirect("/")

	add_to_log("User created", username + " was created automatically")
	create_user(username, password, "", "", False)
	return redirect("/manage")

@app.route("/contest/<contest_name>")
@login_required
def contest_page(contest_name):
	metadata = get_contest_metadata(contest_name)
	if metadata is None:
		return { "error": "Contest not found" }

	if metadata.start_date > time.time() and not current_user.is_admin:
		return render_template("notstarted.html", name=metadata.name)

	return render_template("contest.html")

@app.route("/contest/<contest_name>/question/<question_name>", methods=["GET"])
@login_required
def question_page(contest_name, question_name):
	metadata = get_contest_metadata(contest_name)
	if metadata is None:
		return redirect("/")

	if metadata.start_date > time.time() and not current_user.is_admin:
		return redirect(f"/contest/{contest_name}")

	contest = contest_data[contest_name]
	question = None
	for item in contest["question_data"]:
		if item["short_name"] == question_name:
			question = item
			break
	
	if question is None:
		return { "error": "Question not found" }
	
	return render_template("question.html", question=question, metadata=metadata)

@app.route("/api-submit/<contest_name>/<question_name>", methods=["POST"])
@csrf.exempt
def submit_api(contest_name, question_name):
	metadata = get_contest_metadata(contest_name)
	if metadata is None:
		return redirect("/")

	contest = contest_data[contest_name]
	question = None

	for item in contest["question_data"]:
		if item["short_name"] == question_name:
			question = item
			break

	if question is None:
		return redirect("/")

	data = request.get_json(force=True)

	if not "token" in data or not data["token"] == ADMIN_TOKEN or not "code" in data:
		return redirect("/")

	code = data["code"]
	language = data["language"]
	filename = util.random_string(20) + "." + language
	with open("uploads/" + filename, "w") as f:
		f.write(code)

	test_cases = []
	for item in contest["question_data"]:
		if item["short_name"] != question_name:
			continue

		for tc in item["test_case_data"]:
			test_cases.append(tc)

	user = User.query.filter_by(username=data["user"]).first()
	submit_solution(contest_name, question_name, filename, language, user, test_cases)

	return { "submitted": True }

@app.route("/contest/<contest_name>/question/<question_name>", methods=["POST"])
@login_required
def submit_question(contest_name, question_name):
	metadata = get_contest_metadata(contest_name)
	if metadata is None:
		return redirect("/")
	
	contest = contest_data[contest_name]
	question = None
	for item in contest["question_data"]:
		if item["short_name"] == question_name:
			question = item
			break
	
	if question is None:
		return { "error": "Question not found" }
	
	if time.time() > metadata.end_date:
		return render_template("question.html", question=question, metadata=metadata, error="Contest is complete, you can no longer submit")
	
	if not "solution" in request.files:
		return render_template("question.html", question=question, metadata=metadata, error="No file selected")

	last_submission = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.timestamp.desc()).first()
	if last_submission and time.time() - 60 < last_submission.timestamp:
		return render_template("question.html", question=question, metadata=metadata, error="Please wait one minute between submissions")

	uploaded_file = request.files["solution"]

	if uploaded_file.filename == "":
		return render_template("question.html", question=question, metadata=metadata, error="No file selected")
	
	if uploaded_file.filename.split(".")[-1] not in ACCEPTED_EXTENSIONS:
		return render_template("question.html", question=question, metadata=metadata, error="Invalid file type")
	
	filename = util.random_string(20) + "." + uploaded_file.filename.split(".")[-1]
	uploaded_file.save("uploads/" + filename)

	language = request.form.get("language")

	if language not in LANGUAGE_IDS:
		return render_template("question.html", question=question, metadata=metadata, error="Language not supported")

	test_cases = []
	for item in contest["question_data"]:
		if item["short_name"] != question_name:
			continue

		for tc in item["test_case_data"]:
			test_cases.append(tc)

	add_to_log("Submission", question_name + " (" + contest_name + ") was submitted by " + current_user.username)
	submit_solution(contest_name, question_name, filename, language, current_user, test_cases)

	return redirect("/contest/" + contest_name)

@app.route("/submission/<submission_id>")
@login_required
def submission_page(submission_id):
	submission = Submission.query.filter_by(id=submission_id).first()
	if submission is None:
		return redirect("/")
	
	if not submission.user_id == current_user.id and not current_user.is_admin:
		return redirect("/")

	return render_template("submission.html", submission=submission)

@app.route("/dashboard/<contest_name>")
@login_required
def dashboard_page(contest_name):
	if not current_user.is_admin:
		return redirect("/")

	metadata = get_contest_metadata(contest_name)
	if metadata is None:
		return redirect("/")
	
	return render_template("dashboard.html")

@app.route("/my-team")
@login_required
def my_team():
	team = Team.query.filter_by(id=current_user.team).first()
	if not team:
		return render_template("myteam.html", team=None, users=[])

	users = User.query.filter_by(team=current_user.team)

	return render_template("myteam.html", team=team, users=users)

@app.route("/manage", methods=["GET"])
@login_required
def create_team_page():
	if not current_user.is_admin:
		return redirect("/")

	teams = Team.query.all()
	team_data = []

	for item in teams:
		team_data.append({
			"name": item.name,
			"members": User.query.filter_by(team=item.id).all()
		})

	return render_template("manage.html", teams=team_data, users=User.query.all())

@app.route("/create-team", methods=["GET"])
@login_required
def get_create_team():
	if not current_user.is_admin:
		return redirect("/")

	return render_template("createteam.html")

@app.route("/create-team", methods=["POST"])
@login_required
def create_team():
	if not current_user.is_admin:
		return redirect("/")

	team_name = request.form.get("teamname")
	if not team_name:
		return redirect("/")
	
	team_name = team_name.strip().lower()
	
	if Team.query.filter_by(name=team_name).first() is not None:
		return redirect("/")
	
	team = Team(team_name)
	db.session.add(team)
	db.session.commit()

	add_to_log("Team creation", "Team " + team_name + " was created by " + current_user.username)
	return redirect("/manage")

@app.route("/user/<username>")
@login_required
def user_page(username):
	if not current_user.is_admin:
		return redirect("/")
	
	return render_template("user.html", user=User.query.filter_by(username=username).first(), teams=Team.query.all(), current_team=Team.query.filter_by(id=User.query.filter_by(username=username).first().team).first())

@app.route("/change-time/<contest_name>")
@login_required
def change_time(contest_name):
	pass

@app.route("/change-team/<username>", methods=["POST"])
@login_required
def change_team(username):
	if not current_user.is_admin:
		return redirect("/")

	user = User.query.filter_by(username=username).first()
	if user is None:
		return redirect("/")

	team = request.form.get("teamname")
	if not team:
		return redirect("/")

	if team == "none":
		if user.team is not None:
			add_to_log("Team change", user.username + " was removed from their team by " + current_user.username)
		user.team = None
		db.session.commit()
		return redirect("/manage")

	team = Team.query.filter_by(name=team).first()
	if team is None:
		return redirect("/")

	user.team = team.id
	db.session.commit()
	add_to_log("Team change", user.username + " was added to team " + team.name + " by " + current_user.username)

	return redirect("/manage")

@app.route("/change-times/<contest_name>", methods=["GET"])
@login_required
def get_change_times(contest_name):
	if not current_user.is_admin:
		return redirect("/")

	metadata = get_contest_metadata(contest_name)
	if not metadata:
		return redirect("/")

	return render_template("changetimes.html", start_date=metadata.start_date, end_date=metadata.end_date)

@app.route("/change-times/<contest_name>", methods=["POST"])
@login_required
def change_times(contest_name):
	if not current_user.is_admin:
		return redirect("/")

	contest = Contest.query.filter_by(short_name=contest_name).first()
	if not contest:
		return redirect("/")

	try:
		start = request.json["start_date"]
		end = request.json["end_date"]
	except Exception as e:
		return redirect("/")
	contest.start_date = start
	contest.end_date = end
	db.session.commit()
	add_to_log("Time change", "Contest " + contest_name + " had time changed by " + current_user.username)
	return redirect("/")

@app.route("/submissions/<contest_name>", methods=["GET"])
@login_required
def get_contest_submissions(contest_name):
	if not current_user.is_admin:
		return redirect("/")

	subs = Submission.query.filter_by(contest_name=contest_name).all()
	users = User.query.all()
	user_dict = {}
	cleaned_subs = []
	for u in users:
		user_dict[u.id] = u.username
	for i in subs:
		cleaned_subs.append({ "submission": i, "user": user_dict[i.user_id] })
	cleaned_subs.reverse()
	return render_template("submissions.html", submissions=cleaned_subs)

@app.route("/current-submissions")
@login_required
def get_current_submissions():
	if not current_user.is_admin:
		return redirect("/")
	
	subs = requests.get(GRADER_URL + "/current").json()

	return render_template("currentsubmissions.html", submissions=subs)

@app.route("/request-rate")
@login_required
def get_request_rate():
	if not current_user.is_admin:
		return redirect("/")

	files = os.listdir("request_data")
	files.sort()
	data = {}

	for f in files:
		data[f.split(".")[0]] = json.loads(open("request_data/" + f, "r").read())
	
	return render_template("requestrate.html", rpm=data)

@app.route("/leaderboard")
@login_required
def get_leaderboard():
	if not current_user.is_admin:
		return redirect("/")
	
	return render_template("leaderboard.html")

@app.route("/api/leaderboard")
@login_required
def get_api_leaderboard():
	if not current_user.is_admin:
		return redirect("/")

	ind_contest_name, team_contest_name = "practice_contest", "team_contest"

	user_list = User.query.all()
	students = { i.id: i for i in user_list if "-student-" in i.username }
	teams = {}
	ind_qs = { q: 0 for q in contest_data[ind_contest_name]["questions"] }
	team_qs = { q: 0 for q in contest_data[team_contest_name]["questions"] }

	team_names = {}
	team_objs = Team.query.all()
	for team in team_objs:
		team_names[team.id] = team.name

	for q1 in contest_data[ind_contest_name]["question_data"]:
		for q2 in ind_qs:
			if q1["short_name"] == q2:
				ind_qs[q2] = q1["point_value"]

	for q1 in contest_data[team_contest_name]["question_data"]:
		for q2 in team_qs:
			if q1["short_name"] == q2:
				team_qs[q2] = q1["point_value"]

	for s in students:
		if students[s].team is None:
			continue
		if not students[s].team in teams:
			teams[students[s].team] = {
				"students": {},
				"team_scores": { q: 0 for q in team_qs }
			}
		
		teams[students[s].team]["students"][students[s].username] = { q: 0 for q in ind_qs }

	ind_subs = Submission.query.filter_by(contest_name=ind_contest_name)
	for sub in ind_subs:
		if not sub.user_id in students:
			continue

		user = students[sub.user_id]
		if user.team is None:
			continue
		points_earned = sub.percent_earned / 100 * ind_qs[sub.question]
		team_user = teams[user.team]["students"][user.username]
		team_user[sub.question] = max(team_user[sub.question], points_earned)

	team_subs = Submission.query.filter_by(contest_name=team_contest_name)
	for sub in team_subs:
		if not sub.team_id or not sub.team_id in teams:
			continue

		points_earned = sub.percent_earned / 100 * team_qs[sub.question]
		team = teams[sub.team_id]["team_scores"]
		team[sub.question] = max(team[sub.question], points_earned)

	final_scores = []
	for team in teams:
		totals = []
		for s in teams[team]["students"]:
			totals.append(0)
			for q in teams[team]["students"][s]:
				totals[-1] += teams[team]["students"][s][q]

		avg_ind = sum(totals) / len(totals)
		total_team = 0
		for q in teams[team]["team_scores"]:
			total_team += teams[team]["team_scores"][q]

		final_scores.append((team_names[team], int(avg_ind * 3 + total_team)))

	final_scores.sort(key=lambda i: i[1], reverse=True)
	return final_scores

@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

def create_user(username, password, first, last, is_admin=False):
	user = User(username, bcrypt.generate_password_hash(password).decode("utf-8"), first, last, is_admin)
	db.session.add(user)
	db.session.commit()

def load_contests():
	return Contest.query.all()

def get_contest_metadata(contest_name):
	for item in load_contests():
		if item.short_name == contest_name:
			return item
		
	return None

def submit_solution(contest_id, question, filename, language, user, testcases):
	contest = Contest.query.filter_by(short_name=contest_id).first()
	submission = Submission(contest.short_name, question, "uploads/" + filename, language, user.id, user.team, time.time())
	db.session.add(submission)
	db.session.commit()

	run_code(submission, testcases)

def run_code(submission, testcases):
	with open(submission.filename, "r") as f:
		code = f.read()
	
	response = requests.post(GRADER_URL + "/create-submission", json={
		"code": code,
		"language": LANGUAGE_IDS[submission.language],
		"testcases": testcases
	})
	response = response.json()

	if not "id" in response:
		submission.status = "Completed"
		submission.verdict = "Failed"
		db.session.commit()
		return

	current_submissions.append((submission.id, response["id"]))

if __name__ == "__main__":
	app.run(host="0.0.0.0")
