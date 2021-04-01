from telethon import events
from telethon.tl.types import PeerChannel
from telethon.errors import MessageNotModifiedError
from menus import *
from init import bot, pool, chat_id
from user import BotUser


class SettingsBot:
    def __init__(self):
        self.users = dict()
        bot.on(
            events.NewMessage(
                incoming=True,
                func=self.check_access,
            )
        )(self.handler)
        bot.on(
            events.CallbackQuery(
                func=self.check_access,
            )
        )(self.buttons_handler)

    def __await__(self):
        return self._prepare_users().__await__()

    async def _prepare_users(self):
        for record in await pool.fetch('SELECT * FROM users'):
            self.users[record['id']] = BotUser(record['id'])
            self.users[record['id']].cache(**record)
        return self

    @staticmethod
    async def check_access(event):
        participants = await bot.get_participants(PeerChannel(chat_id))
        participants_id = [user.id for user in participants]
        if event.sender.id in participants_id:
            return True
        else:
            await bot.send_message(event.sender, 'Отказано в доступе.')

    def get_user(self, user_id):
        if user_id not in self.users:
            self.users[user_id] = BotUser(user_id)
        return self.users[user_id]

    async def handler(self, event):
        user = self.get_user(event.sender.id)

        text = event.text.lower()

        disposable_handler = user.disposable_handler
        user.disposable_handler = None

        try:

            if text == '/start' or text == 'главное меню':
                await General.menu(user)

            elif text == '/status' or text == 'статус':
                await General.status(
                    user, general=True if text == 'статус' else False)

            elif text == '/settings' or text == 'настройки':
                await General.Settings.menu(user)

            elif text == '/log_in' or text == 'авторизоваться':
                if event.sender.phone:
                    user.phone = event.sender.phone
                await General.LogIn.menu(user)

            elif text == '/exit' or text == 'выйти':
                await General.Exit.menu(user)

            elif text == '/on':
                await General.Settings.on(user)

            elif text == '/off':
                await General.Settings.off(user)

            elif text == '/help':
                await General.help(user)

            elif disposable_handler:
                await disposable_handler(user, event)
            else:
                await user.reply('Меня к такому не готовили \U0001F630\n'
                                 'Воспользуйтесь: /help')

        except Exception as e:
            print('handler Ex: ', e)
            await user.reply(str(e))

    async def buttons_handler(self, event):
        user = self.get_user(event.sender.id)
        user.disposable_handler = None
        data = event.data.decode('utf-8')
        obj = General
        for attr in re.findall(r'\.(\w+)[^&.]?', data):
            obj = getattr(obj, attr)
        try:
            await obj(user, event)
        except MessageNotModifiedError:
            print(MessageNotModifiedError)
        except Exception as e:
            print('buttons_handler Ex:', e)
            await user.reply(str(e))


async def main():
    await SettingsBot()
    await bot.run_until_disconnected()
    await pool.close()


if __name__ == '__main__':
    bot.loop.run_until_complete(main())
