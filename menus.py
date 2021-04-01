from telethon import TelegramClient, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, \
    PasswordHashInvalidError, PhoneCodeInvalidError
from telethon.events.newmessage import NewMessage
from telethon.events.callbackquery import CallbackQuery
import re
from init import api_id, api_hash
from user import BotUser


def build_buttons(markup: list, builder=Button.inline):
    return list(
        map(
            lambda i: builder(*i) if not isinstance(i, list)
            else build_buttons(i, builder),
            markup
        )
    )


class General:
    @staticmethod
    async def menu(user, event=None, text='Главное меню:', is_logged_in=None):
        if is_logged_in is None:
            is_logged_in = await user.check_authorization()
        buttons = [
            'Статус',
            'Настройки',
            'Выйти' if is_logged_in else 'Авторизоваться'
        ]
        markup = [
            [Button.text(button, resize=True, single_use=True)]
            for button in buttons
        ]
        if event:
            await event.delete()
        return await user.reply(text, buttons=markup)

    @staticmethod
    async def status(user, general=None):
        values = await user.get(
            *['session', 'switch', 'circuit_breaker',
              'answer', 'gender', 'filters'])
        session, switch, circuit_breaker, answer, gender, filters = values
        is_user_logged_in = await user.check_authorization(session=session)
        rows = [
            'Статус: __' +
            ('работает' if switch and is_user_logged_in else 'выключен') + '__',

            'Авторизация: __' +
            ('есть' if is_user_logged_in else 'отсутствует') + '__',

            'Сообщение-ответ: __' +
            ('\n' + answer if answer else '*не задано*') + '__',

            'Автоматический выключатель: __' +
            ('включен' if circuit_breaker else 'выключен') + '__',

            'Пол: __' + (gender if gender else 'не выбран') + '__',
            'Стоп фразы: __' + (
                '__, __'.join(filters) if len(filters) else '*не заданы*'
            ) + '__'
        ]
        text = '\n'.join(rows)
        if general:
            await General.menu(user, text=text, is_logged_in=is_user_logged_in)
        else:
            await user.reply(text)

    @staticmethod
    async def help(user):
        text = '/start - Главное меню\n\n' \
               '/status - Текущие параметры\n' \
               '/settings - Меню настроек\n\n' \
               '/log_in - Авторизоваться\n' \
               '/exit - Выйти\n\n' \
               '/on - Активировать автоответчик\n' \
               '/off - Деактивировать автоответчик'
        await user.reply(text)

    class Settings:
        @classmethod
        async def menu(cls,
                       user: BotUser,
                       event=None,
                       text='Меню настроек:',
                       switch=None):
            switch = await user.get('switch') if switch is None else switch
            markup = [
                [
                    ('Выключить', cls.off.__qualname__) if switch
                    else ('Включить', cls.on.__qualname__),
                    ('Сообщение-ответ', cls.Answer.menu.__qualname__)
                ], [
                    ('Автоматический выключатель',
                     cls.CircuitBreaker.menu.__qualname__)
                ], [
                    ('Фильтр по полу', cls.Gender.menu.__qualname__),
                    ('Кастомный фильтр', cls.Filters.menu.__qualname__)
                ], [
                    ('Главное меню', General.menu.__qualname__)
                ]
            ]
            reply = event.edit if isinstance(event, CallbackQuery.Event) \
                else user.reply
            await reply(text, buttons=build_buttons(markup))

        @classmethod
        async def off(cls, user: BotUser, event=None):
            if event is None:
                await user.reply('Автоматическая запись деактивирована.')
            else:
                await cls.menu(user, event, switch=False)
            await user.set(switch=False)

        @classmethod
        async def on(cls, user: BotUser, event=None):
            if await user.check_authorization():
                if event is None:
                    await user.reply('Автоматическая запись активирована.')
                else:
                    await cls.menu(user, event, switch=True)
                await user.set(switch=True)
            else:
                text = 'Для активации автоматической записи ' \
                       'необходимо авторизоваться.\n' \
                       'Воспользуйтесь: /log_in'
                if event is None:
                    await user.reply(text)
                else:
                    await event.answer('Отказано')
                    await cls.menu(user, event, text=text, switch=False)
                await user.set(switch=False)

        class Answer:
            @classmethod
            async def menu(cls, user: BotUser, event=None):
                answer = await user.get('answer')
                text = 'Текущее сообщение, автоматически отправляемое ' \
                       'при наборе людей на мероприятие:\n__' + \
                       (answer if answer else '*не задано*') + '__'
                markup = [
                    ('Именить', cls.edit.__qualname__),
                    ('Назад', General.Settings.menu.__qualname__)
                ]
                reply = event.edit if event else user.reply
                await reply(text, buttons=build_buttons(markup))

            @classmethod
            async def edit(cls, user: BotUser, event):
                text = 'Введите сообщение, которое будет автоматически ' \
                       'отправляться при наборе людей на мероприятие. ' \
                       'Например: \n__+380123456789 - Герман__'
                await event.delete()
                await user.reply(
                    text,
                    buttons=Button.text(
                        'Отмена',
                        resize=True,
                        single_use=True)
                )
                user.disposable_handler = cls.set

            @classmethod
            async def set(cls, user: BotUser, event):
                if event.text != 'Отмена':
                    if event.text:
                        await user.set(answer=event.text)
                    await cls.menu(user)
                else:
                    await General.Settings.menu(
                        user,
                        text='Изменение сообщения-ответа было отменено.'
                    )

        class CircuitBreaker:
            @classmethod
            async def menu(cls, user: BotUser, event, circuit_breaker=None):
                circuit_breaker = await user.get('circuit_breaker') \
                    if circuit_breaker is None else circuit_breaker
                text = 'Если включен, автоматически приостанавливает работу ' \
                       'автоответчика сразу после успешной записи на ' \
                       'мероприятие, на заданный период времени или ' \
                       'до ручной активации, если тайм-аут не задан.'
                markup = [[('Выключить', cls.off.__qualname__)
                           if circuit_breaker else
                           ('Включить', cls.on.__qualname__),
                           # ('Тайм-аут', )],
                           ('Назад', General.Settings.menu.__qualname__)]]
                await event.edit(text, buttons=build_buttons(markup))

            @classmethod
            async def off(cls, user: BotUser, event):
                await cls.menu(user, event, circuit_breaker=False)
                await user.set(circuit_breaker=False)

            @classmethod
            async def on(cls, user: BotUser, event):
                await cls.menu(user, event, circuit_breaker=True)
                await user.set(circuit_breaker=True)

        class Gender:
            @classmethod
            async def menu(cls, user: BotUser, event=None, gender=None):
                gender = await user.get('gender') if gender is None else gender
                text = 'Фильтрует запись на мероприятия по половой ' \
                       'принадлежности, если она выбрана.\n' \
                       'Текущий пол: __' + (
                           gender if gender else 'не выбран') + '__'
                markup = [('Выбрать пол', cls.edit.__qualname__),
                          ('Назад', General.Settings.menu.__qualname__)]
                reply = event.edit if event else user.reply
                await reply(text, buttons=build_buttons(markup))

            @classmethod
            async def edit(cls, user: BotUser, event):
                gender: str = await user.get('gender')
                male = ('Мужской', cls.male.__qualname__)
                female = ('Женский', cls.female.__qualname__)
                undefined = ('Удалить фильтр', cls.undefined.__qualname__)
                markups = {'Мужской': [female, undefined],
                           'Женский': [male, undefined],
                           None: [male, female]}
                markup = [markups[gender],
                          [('Отмена', General.Settings.menu.__qualname__)]]
                await event.edit('Выберите пол:', buttons=build_buttons(markup))

            @classmethod
            async def male(cls, user: BotUser, event):
                await cls.menu(user, event, gender='Мужской')
                await user.set(gender='Мужской')

            @classmethod
            async def female(cls, user: BotUser, event):
                await cls.menu(user, event, gender='Женский')
                await user.set(gender='Женский')

            @classmethod
            async def undefined(cls, user: BotUser, event):
                await cls.menu(user, event, gender=False)
                await user.set(gender=None)

        class Filters:
            @classmethod
            async def menu(cls, user: BotUser, event=None, filters=None,
                           index=None):
                filters = await user.get(
                    'filters') if filters is None else filters
                text = 'Позволяет задавать стоп-фразы.\n' \
                       'Набор на мероприятие, включающий в себя одну из фраз, '\
                       'будет проигнорирован.'
                markup = [*[[(filters[i], cls.edit.__qualname__ + '&' + str(i))]
                            for i in range(len(filters))],
                          [('Добавить фразу', cls.add.__qualname__),
                           ('Назад', General.Settings.menu.__qualname__)]]
                if isinstance(index, int):
                    markup[index] = [
                        ('Удалить', cls.delete.__qualname__ + '&' + str(index)),
                        ('Отмена', cls.menu.__qualname__)]
                reply = event.edit if event else user.reply
                await reply(text, buttons=build_buttons(markup))

            @classmethod
            async def add(cls, user: BotUser, event):
                text = 'Введите стоп-фразу. Регистр не имеет значения.\n' \
                       'Например: __с пушки__ или __на сейчас__'
                await event.delete()
                await user.reply(text, buttons=Button.text(
                    'Отмена', resize=True, single_use=True))
                user.disposable_handler = cls.set

            @classmethod
            async def set(cls, user: BotUser, event):
                if event.text != 'Отмена':
                    if len(event.text) > 1:
                        filters = user.filters + [event.text]
                        await cls.menu(user, filters=filters)
                        await user.set(filters=filters)
                    else:
                        text = 'Слишком мало символов. Попробуйте еще.'
                        button = Button.text('Отмена', resize=True,
                                             single_use=True)
                        await user.reply(text, buttons=button)
                        user.disposable_handler = cls.set
                else:
                    await cls.menu(user)

            @classmethod
            async def edit(cls, user: BotUser, event):
                index = int(
                    re.findall(r'&(\w+)', event.data.decode('utf-8'))[0])
                await cls.menu(user, event, filters=user.filters, index=index)

            @classmethod
            async def delete(cls, user: BotUser, event):
                index = int(
                    re.findall(r'&(\w+)', event.data.decode('utf-8'))[0])
                del user.filters[index]
                await cls.menu(user, event, filters=user.filters)
                await user.set(filters=user.filters)

    class LogIn:
        @classmethod
        async def menu(cls, user: BotUser, event=None,
                       text='Отправьте свой телефонный номер.'):
            user.client = TelegramClient(StringSession(), api_id, api_hash)
            user.code = ''
            if hasattr(user, 'phone') and user.phone:
                await cls.set_code(user)
                await user.client.connect()
                await user.client.send_code_request(user.phone)
            else:
                user.disposable_handler = cls.set_phone
                markup = [
                    [Button.request_phone('Отправить мой номер \U0000260E')],
                    [Button.text('Отмена', resize=True, single_use=True)]]
                reply = event.edit if event else user.reply
                await reply(text, buttons=markup)

        @classmethod
        async def set_phone(cls, user: BotUser, event):
            if event.text == 'Отмена':
                await cls.cancel(user)
                return

            if event.contact:
                user.phone = event.media.phone_number
                await cls.set_code(user)
                await user.client.connect()
                await user.client.send_code_request(user.phone)
            else:
                await cls.menu(user)

        @classmethod
        async def set_code(cls, user: BotUser, event=None,
                           text='Вам был отправлен код авторизации.'):
            markup = [[('Ввести код', cls.enter_code.__qualname__),
                       ('Отмена', cls.cancel.__qualname__)],
                      [('Отправить смс с кодом',
                        cls.send_sms_code.__qualname__)]]

            reply = event.edit if event else user.reply
            await reply(text, buttons=build_buttons(markup))

        @staticmethod
        async def cancel(user: BotUser, event=None):
            if event:
                await event.delete()
            await General.menu(user, text='Авторизация была отменена.')

        @classmethod
        async def send_sms_code(cls, user: BotUser, event: CallbackQuery.Event):
            msg = await event.get_message()
            await event.edit(msg.text)
            text = 'Вам было отправлено СМС с кодом авторизации.'
            await cls.set_code(user, text=text)
            await user.client.connect()
            await user.client.send_code_request(user.phone, force_sms=True)

        @classmethod
        async def enter_code(cls, user: BotUser, event=None):
            reply = user.reply
            if event:
                if event.data == b'enter_code':
                    msg = await event.get_message()
                    await event.edit(msg.text)
                else:
                    reply = event.edit

            num_keyboard = [
                ['1', '2', '3'],
                ['4', '5', '6'],
                ['7', '8', '9'],
                ['x', '0', '<']
            ]
            markup = build_buttons(
                num_keyboard,
                builder=lambda i: Button.inline(
                    i, cls.enter_num.__qualname__ + '&' + i
                )
            )
            text = ' '.join([
                'Введите код:\n      ',
                *('*' * len(user.code)),
                *('_' * (5 - len(user.code)))
            ])
            return await reply(text, buttons=markup)

        @classmethod
        async def enter_num(cls, user: BotUser, event):
            data = re.findall(r'&(.+)', event.data.decode('utf-8'))[0]
            if 'x' == data:
                if user.code == '':
                    await cls.set_code(
                        user,
                        event,
                        text='Ввод кода был отменен.'
                    )
                    return
                user.code = ''
            elif '<' == data and len(user.code) > 1:
                user.code = user.code[:-1]
            else:
                user.code += data

            await event.answer('Код: {}'.format(
                user.code + '_' * (5 - len(user.code))))
            await cls.enter_code(user, event)

            if len(user.code) >= 5:
                await cls.sign_in(user, event)

        @classmethod
        async def sign_in(cls, user: BotUser, event):
            try:
                await user.client.sign_in(user.phone, user.code)
                if await user.client.is_user_authorized():
                    await cls.save_session(user, event)

            except PhoneCodeInvalidError:
                await event.edit('Код недействителен. Попробуйте снова.')
                user.code = ''
                await cls.enter_code(user)

            except SessionPasswordNeededError:
                user.disposable_handler = cls.two_step_verification
                await event.delete()
                await user.reply(
                    'Введите пароль двухэтапной аутентификации.',
                    buttons=Button.text('Отмена', single_use=True, resize=True))

        @classmethod
        async def two_step_verification(cls,
                                        user: BotUser,
                                        event: NewMessage.Event):
            if event.text == 'Отмена':
                await cls.cancel(user)
                return

            try:
                await user.client.sign_in(password=event.text)
                await cls.save_session(user)

            except PasswordHashInvalidError:
                user.disposable_handler = cls.two_step_verification
                await user.reply(
                    'Введенный вами пароль недействителен. Попробуйте снова.',
                    buttons=Button.text('Отмена', single_use=True, resize=True))

        @classmethod
        async def save_session(cls, user: BotUser, event=None):
            if await user.client.is_user_authorized():
                if event:
                    await event.delete()
                name = (await user.client.get_me()).username
                session = StringSession.save(user.client.session)
                await user.set(session=session)
                await General.menu(user,
                                   text=f'Добро пожаловать, {name}',
                                   is_logged_in=True)

                if not await user.get('answer'):
                    await user.set(answer=user.phone)
            else:
                await cls.set_code(
                    user, event, 'Не удалось авторизоваться. Попробуте снова.')

    class Exit:
        @classmethod
        async def menu(cls, user: BotUser):
            text = 'Ваш ключ авторизации будет удален.\n' \
                   'Вы действительно хотите выйти?'
            markup = [('Да', cls.yes.__qualname__),
                      ('Нет', cls.no.__qualname__)]
            await user.reply(text, buttons=build_buttons(markup))

        @classmethod
        async def yes(cls, user: BotUser, event):
            text = 'Удалить все настройки?'
            markup = [[('Оставить', cls.leave.__qualname__),
                       ('Удалить', cls.delete.__qualname__)],
                      [('Отмена', cls.no.__qualname__)]]
            await event.edit(text, buttons=build_buttons(markup))

        @staticmethod
        async def no(user: BotUser, event):
            await event.delete()
            await General.menu(user, text='Выход был отменён.')

        @staticmethod
        async def leave(user: BotUser, event):
            await event.delete()
            text = 'Ключ авторизации был удален.'
            await General.menu(user, text=text, is_logged_in=False)
            await user.set(session=None)

        @staticmethod
        async def delete(user: BotUser, event):
            await event.delete()
            text = 'Ключ авторизации и все настройки были удалены.'
            await General.menu(user, text=text, is_logged_in=False)
            await user.set(
                session=None, switch=False, answer=None, gender=None,
                circuit_breaker=True, filters=[])
