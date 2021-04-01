from telethon import TelegramClient
from telethon.sessions import StringSession
from init import api_id, api_hash, bot, pool


class User:
    def __init__(self, user_id: int):
        self.__id = user_id

    @property
    def id(self):
        return self.__id

    async def check_authorization(self, session: str) -> bool:
        if isinstance(session, str) and len(session) == 353:
            client = TelegramClient(
                StringSession(session),
                api_id,
                api_hash
            )
            await client.connect()
            if await client.is_user_authorized():
                return True
            else:
                await self.authorization_lost()
            await client.disconnect()

        else:
            await self.authorization_lost()
            raise TypeError(
                '"session" must be derived from telethon.StringSession.'
            )

    async def authorization_lost(self):
        await bot.send_message(
            self.id,
            'Ключ авторизации недействителен, '
            'необходима повторная авторизация.\n'
            'Воспользуйтесь: /log_in'
        )
        await pool.execute(
            f'UPDATE users SET session = NULL WHERE id = {self.id}'
        )


class Cache(User):
    session: str
    switch: bool
    circuit_breaker: bool
    answer: str
    gender: str
    filters = dict()

    logged_in = None

    def cache(self, **kwargs) -> None:
        if kwargs and 'id' in kwargs:
            del kwargs['id']
        for var, val in kwargs.items():
            setattr(self, var, val)

    async def check_authorization(self, session: str) -> bool:
        logged_in = await super().check_authorization(session)
        self.cache(logged_in=logged_in)
        return logged_in


class DataBase:
    id: int

    async def _add_user(self: User, connection=pool):
        await connection.execute(f'INSERT INTO users (id) VALUES ({self.id})')

    async def get(self, *variables, connection=pool):
        record = await connection.fetchrow(
            f"SELECT * FROM users WHERE id = {self.id}")
        if record is None:
            await self._add_user(connection)
            return await DataBase.get(self, *variables, connection=connection)
        if not variables:
            return record
        values = tuple(record[var] for var in variables)
        return values[0] if len(values) == 1 else values

    async def set(self, *, connection=pool, **kwargs) -> bool:
        variables, values, i = list(), list(), 0
        for var, val in kwargs.items():
            i += 1
            variables.append(var + f' = ${i}')
            values.append(val)
        args = ", ".join(variables)

        command = f"UPDATE users SET {args} WHERE id = {self.id}"
        if 'UPDATE 0' == await connection.execute(command, *values):
            await self._add_user(connection)
            return await DataBase.set(self, connection=pool, **kwargs)
        return True


class LogIn:
    client: TelegramClient
    phone: str
    code = ''


class BotUser(Cache, DataBase, LogIn):
    disposable_handler = None

    async def reply(self: User, text, buttons=None, **kwargs):
        return await bot.send_message(self.id, text, buttons=buttons, **kwargs)

    async def get(self, *variables: str):
        values = await super().get(*variables)
        args = dict(zip(variables, [values] if len(variables) == 1 else values))
        self.cache(**args)
        return values

    async def set(self, **kwargs) -> bool:
        if await super().set(**kwargs):
            self.cache(**kwargs)
            return True

    async def check_authorization(self, session: str = None) -> bool:
        session = await self.get('session') if not session else session
        return await super().check_authorization(session)
