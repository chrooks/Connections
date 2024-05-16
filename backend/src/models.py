from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Game(db.Model):
    id = db.Column(db.String, primary_key=True)
    grid = db.Column(db.PickleType)
    relationships = db.Column(db.PickleType)
    remaining_guesses = db.Column(db.Integer)
    game_over = db.Column(db.Boolean)

    def __repr__(self):
        return '<Game %r>' % self.id