import random
import re
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from config import TOKEN, DSN
from base import Words, Users, UserWords

print('Start telegram bot...')

state_storage = StateMemoryStorage()
bot = TeleBot(TOKEN, state_storage=state_storage)

engine = create_engine(DSN)
Session = sessionmaker(bind=engine)


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    adding_target_word = State()
    adding_translate_word = State()
    deleting_word = State()


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово 🔙'
    NEXT = 'Дальше ⏭'


def get_session_pair(session):
    pair = session.query(Words.target_word, Words.translate_word).order_by(func.random()).first()
    return pair


def get_random_words(session, exclude_word, limit=3):
    random_words = session.query(Words.target_word).filter(Words.target_word != exclude_word).order_by(
        func.random()).limit(limit).all()
    return [word[0] for word in random_words]


def validate_input(user_input):
    return re.match(r'^[а-яА-ЯёЁa-zA-Z\s]+$', user_input) is not None


def create_keyboard(*buttons):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for i in range(0, len(buttons), 2):
        row_buttons = [types.KeyboardButton(buttons[i])]
        if i + 1 < len(buttons):
            row_buttons.append(types.KeyboardButton(buttons[i + 1]))
        markup.add(*row_buttons)
    return markup


@bot.message_handler(commands=['start'])
def greetings(message):
    chat_id = message.chat.id
    bot.send_message(chat_id,
                     'Привет, я бот для самостоятельного изучения английского языка🙈\n\n'
                     'У тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения\n\n'
                     'Для этого воспрользуйся инструментами:  добавить слово ➕, удалить слово 🔙.\n\n'
                     'Чтобы получить карточки переводов отправьте "/cards"')


@bot.message_handler(commands=['cards'])
def create_cards(message):
    cid = message.chat.id

    # Получение случайной пары (слово и его перевод)
    session = Session()
    pair = get_session_pair(session)
    session.close()

    if not pair:
        bot.send_message(cid, "Ошибка: не удалось получить случайное слово.")
        return

    target_word = pair[0]
    print(target_word)
    translate = pair[1]
    print(translate)

    session = Session()
    others = get_random_words(session, target_word)
    print(others)
    session.close()

    options = others + [target_word]
    print(options)
    print(len(options))
    random.shuffle(options)
    options.extend([Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD])
    print(options)
    markup = create_keyboard(*options)

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(cid, greeting, reply_markup=markup)

    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    bot.send_message(message.chat.id, "Введите слово на английском, которое хотите удалить:")
    bot.set_state(message.from_user.id, MyStates.deleting_word, message.chat.id)


@bot.message_handler(state=MyStates.deleting_word)
def handle_delete_word(message):
    if validate_input(message.text):
        target_word = message.text
        session = Session()
        try:
            user_id = get_or_create_user(session, message.chat.id, message.from_user.username)

            word = session.query(Words).filter_by(target_word=target_word).first()
            if word:

                user_word = session.query(UserWords).filter_by(word_id=word.word_id, user_id=user_id).first()
                if user_word:
                    # Удаление записей из UserWords, связанных с этим словом
                    session.delete(user_word)
                    session.delete(word)
                    session.commit()
                    bot.send_message(message.chat.id, f"Слово '{target_word}' удалено.")
                else:
                    bot.send_message(message.chat.id, "Вы не можете удалить это слово, так как оно не принадлежит вам.")
            else:
                bot.send_message(message.chat.id, "Слово не найдено в базе данных.")
        except Exception as e:
            session.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка: {e}")
        finally:
            session.close()
        bot.delete_state(message.from_user.id, message.chat.id)
    else:
        bot.send_message(message.chat.id,
                         "Ошибка: слово не должно содержать цифр и специальных символов. Попробуйте снова.")


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    bot.send_message(message.chat.id, "Введите новое слово:")
    bot.set_state(message.from_user.id, MyStates.adding_target_word, message.chat.id)


@bot.message_handler(state=MyStates.adding_target_word)
def handle_new_word(message):
    if validate_input(message.text):
        target_word = message.text
        bot.send_message(message.chat.id, "Введите перевод слова:")
        bot.set_state(message.from_user.id, MyStates.adding_translate_word, message.chat.id)

        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word'] = target_word
    else:
        bot.send_message(message.chat.id,
                         "Ошибка: слово не должно содержать цифр и специальных символов. Попробуйте снова.")


@bot.message_handler(state=MyStates.adding_translate_word)
def get_translate_word(message):
    if validate_input(message.text):
        session = Session()
        try:
            with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                target_word = data.get('target_word')
                translate_word = message.text
                user_id = get_or_create_user(session, message.chat.id, message.from_user.username)
                word = session.query(Words).filter_by(target_word=target_word).first()
                if word:
                    if word.translate_word != translate_word:
                        word.translate_word = translate_word
                        session.commit()
                        bot.send_message(message.chat.id,
                                         f"Перевод для слова '{target_word}' обновлён на '{translate_word}'.")
                else:
                    word = Words(target_word=target_word, translate_word=translate_word)
                    session.add(word)
                    session.commit()
                    user_word = UserWords(user_id=user_id, word_id=word.word_id)
                    session.add(user_word)
                    session.commit()
                    bot.send_message(message.chat.id,
                                     f"Слово '{target_word}' с переводом '{translate_word}' добавлено в базу данных для пользователя.")
        except Exception as e:
            session.rollback()
            bot.send_message(message.chat.id, f"Произошла ошибка: {e}")
        finally:
            session.close()
        bot.delete_state(message.from_user.id, message.chat.id)
    else:
        bot.send_message(message.chat.id,
                         "Ошибка: перевод не должен содержать цифр и специальных символов. Попробуйте снова.")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = create_keyboard(Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            hint = f"Отлично!❤\n{target_word} -> {data['translate_word']}"
        else:
            hint = "Допущена ошибка!\nПопробуй ещё раз."
    bot.send_message(message.chat.id, hint, reply_markup=markup)


def get_or_create_user(session, chat_id, username):
    user = session.query(Users).filter_by(chat_id=chat_id).first()
    if not user:
        user = Users(chat_id=chat_id, username=username)
        session.add(user)
        session.commit()
    return user.user_id


bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.infinity_polling(skip_pending=True)
