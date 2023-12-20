def deploy():
	from app import create_app, db
	from flask_migrate import upgrade, migrate, init, stamp
	
	app = create_app()
	app.app_context().push()

	if input("Are you sure you want to delete all tables and data? (y/n) ").lower() == "y":
		db.drop_all()
	db.create_all()

	init()
	stamp()
	migrate()
	upgrade()

deploy()