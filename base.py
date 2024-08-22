import sqlalchemy as sq
import sqlalchemy.exc
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import create_engine, ForeignKey, text
from config import DSN

Base = declarative_base()

class UserWords(Base):
    __tablename__ = "user_words"

    user_word_id = sq.Column(sq.Integer, primary_key=True)
    is_learned = sq.Column(sq.Boolean, default=False)

    user_id = sq.Column(sq.Integer, ForeignKey("users.user_id"), nullable=False)
    word_id = sq.Column(sq.Integer, ForeignKey("words.word_id"), nullable=False)

    user = relationship("Users", back_populates="user_words")
    word = relationship("Words", back_populates="user_words")

class Users(Base):
    __tablename__ = "users"

    user_id = sq.Column(sq.Integer, primary_key=True)
    chat_id = sq.Column(sq.BigInteger, nullable=False, unique=True)
    username = sq.Column(sq.String(length=40), nullable=False, unique=True)
    user_words = relationship("UserWords", back_populates="user")

class Words(Base):
    __tablename__ = "words"

    word_id = sq.Column(sq.Integer, primary_key=True)
    target_word = sq.Column(sq.Text, nullable=False, unique=True)
    translate_word = sq.Column(sq.Text, nullable=False, unique=True)
    user_words = relationship("UserWords", back_populates="word")

def create_tables():
    engine = create_engine(DSN)
    Base.metadata.create_all(engine)
    print("Таблицы успешно созданы")
    return engine

def initial_words(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Очистка базы данных...")
    try:
        # Очистка таблиц через ORM
        session.query(UserWords).delete(synchronize_session=False)
        session.query(Words).delete(synchronize_session=False)
        session.commit()

        print("База данных успешно очищена")
    except sqlalchemy.exc.SQLAlchemyError as e:
        session.rollback()
        print(f"Ошибка при очистке базы данных: {e}")
        return

    initial_words_data = [
        {"target_word": "Sun", "translate_word": "Солнце"},
        {"target_word": "Blue", "translate_word": "Голубой"},
        {"target_word": "We", "translate_word": "Мы"},
        {"target_word": "Sky", "translate_word": "Небо"},
        {"target_word": "Dog", "translate_word": "Собака"},
        {"target_word": "View", "translate_word": "Вид"},
        {"target_word": "Ocean", "translate_word": "Океан"},
        {"target_word": "Storm", "translate_word": "Шторм"},
        {"target_word": "Apple", "translate_word": "Яблоко"},
        {"target_word": "Human", "translate_word": "Человек"},
    ]

    try:
        # Использование bulk_insert_mappings для быстрой вставки данных
        session.execute(
            Words.__table__.insert(),
            initial_words_data
        )
        session.commit()
        print("Начальная база переводов добавлена")
    except sqlalchemy.exc.IntegrityError as e:
        session.rollback()
        print(f"Ошибка при добавлении данных: {e}")

    session.close()

if __name__ == "__main__":
    engine = create_tables()
    initial_words(engine)