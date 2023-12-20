from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa

db = SQLAlchemy()

class User(UserMixin, db.Model):
	__tablename__ = "users"

	id = sa.Column(sa.Integer, primary_key=True)
	username = sa.Column(sa.String(100), unique=True)
	password = sa.Column(sa.String(100))
	first = sa.Column(sa.String(100))
	last = sa.Column(sa.String(100))
	team = sa.Column(sa.Integer, sa.ForeignKey("teams.id"))
	is_admin = sa.Column(sa.Boolean)
	submissions = db.relationship("Submission", backref="user")

	def __init__(self, username, password, first, last, is_admin):
		self.username = username
		self.password = password
		self.first = first
		self.last = last
		self.is_admin = is_admin

class Team(db.Model):
	__tablename__ = "teams"

	id = sa.Column(sa.Integer, primary_key=True)
	name = sa.Column(sa.String(100))
	users = db.relationship("User", backref="user_team")

	def __init__(self, name):
		self.name = name

class Contest(db.Model):
	__tablename__ = "contests"

	id = sa.Column(sa.Integer, primary_key=True)
	name = sa.Column(sa.String(100))
	short_name = sa.Column(sa.String(100))
	individual = sa.Column(sa.Boolean)
	start_date = sa.Column(sa.Integer)
	end_date = sa.Column(sa.Integer)

	def __init__(self, name, short_name, individual, start_date, end_date):
		self.name = name
		self.short_name = short_name
		self.individual = individual
		self.start_date = start_date
		self.end_date = end_date

class Submission(db.Model):
	__tablename__ = "submissions"

	id = sa.Column(sa.Integer, primary_key=True)
	contest_name = sa.Column(sa.String(100))
	question = sa.Column(sa.String(100))
	filename = sa.Column(sa.String(100))
	language = sa.Column(sa.String(100))
	user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"))
	team_id = sa.Column(sa.Integer, sa.ForeignKey("teams.id"))
	timestamp = sa.Column(sa.Integer)
	status = sa.Column(sa.String(100))
	verdict = sa.Column(sa.String(100))
	percent_earned = sa.Column(sa.Integer)

	def __init__(self, contest_id, question, filename, language, user_id, team_id, timestamp):
		self.contest_name = contest_id
		self.question = question
		self.filename = filename
		self.language = language
		self.user_id = user_id
		self.team_id = team_id
		self.timestamp = timestamp
		self.status = "In queue"
		self.verdict = "Pending"
		self.percent_earned = 0