from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class BaseModelo(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=BaseModelo)
migrate = Migrate()
jwt = JWTManager()
