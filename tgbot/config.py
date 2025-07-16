from dataclasses import dataclass
from typing import Optional, List

from environs import Env
from sqlalchemy import URL


@dataclass
class TgBot:
    """
    Creates the TgBot object from environment variables.

    Attributes
    ----------
    token : str
        The bot token.
    use_redis : str
        If we need to use redis.
    division : str
        Division where bot will run.
    """

    token: str
    admin_ids: list[int]
    use_redis: bool

    forum_id: str

    activity_status: bool
    activity_warn_minutes: int
    activity_close_minutes: int

    @staticmethod
    def from_env(env: Env):
        """
        Creates the TgBot object from environment variables.
        """
        token = env.str("BOT_TOKEN")

        # @TODO Replace admin_ids with db users which have role 10
        admin_ids = env.list("ADMINS", subcast=int)

        use_redis = env.bool("USE_REDIS")

        forum_id = env.str("FORUM_ID")

        activity_status = env.bool("ACTIVITY_STATUS")
        activity_warn_minutes = env.int("ACTIVITY_WARN_MINUTES")
        activity_close_minutes = env.int("ACTIVITY_CLOSE_MINUTES")

        return TgBot(
            token=token,
            admin_ids=admin_ids,
            use_redis=use_redis,
            forum_id=forum_id,
            activity_status=activity_status,
            activity_warn_minutes=activity_warn_minutes,
            activity_close_minutes=activity_close_minutes,
        )


@dataclass
class DbConfig:
    """
    Database configuration class.
    This class holds the settings for the database, such as host, password, port, etc.

    Attributes
    ----------
    host : str
        The host where the database server is located.
    password : str
        The password used to authenticate with the database.
    user : str
        The username used to authenticate with the database.
    main_db : str
        The name of the main database.
    ntp_achievements_db : str
        The name of the ntp achievements database.
    nck_achievements_db : str
        The name of the nck achievements database.
    """

    host: str
    user: str
    password: str

    main_db: str

    def construct_sqlalchemy_url(
        self,
        db_name=None,
        driver="aioodbc",
    ) -> URL:
        """
        Constructs and returns a SQLAlchemy URL for SQL Server database configuration.
        """
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={self.host};"
            f"DATABASE={db_name if db_name else self.main_db};"
            f"UID={self.user};"
            f"PWD={self.password};"
            f"TrustServerCertificate=yes;"
        )
        connection_url = URL.create(
            f"mssql+{driver}", query={"odbc_connect": connection_string}
        )

        return connection_url

    @staticmethod
    def from_env(env: Env):
        """
        Creates the DbConfig object from environment variables.
        """
        host = env.str("DB_HOST")
        user = env.str("DB_USER")
        password = env.str("DB_PASS")

        main_db = env.str("DB_MAIN_NAME")

        return DbConfig(host=host, user=user, password=password, main_db=main_db)


@dataclass
class RedisConfig:
    """
    Redis configuration class.

    Attributes
    ----------
    redis_pass : Optional(str)
        The password used to authenticate with Redis.
    redis_port : Optional(int)
        The port where Redis server is listening.
    redis_host : Optional(str)
        The host where Redis server is located.
    """

    redis_pass: Optional[str]
    redis_port: Optional[int]
    redis_host: Optional[str]

    def dsn(self) -> str:
        """
        Constructs and returns a Redis DSN (Data Source Name) for this database configuration.
        """
        if self.redis_pass:
            return f"redis://:{self.redis_pass}@{self.redis_host}:{self.redis_port}/0"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/0"

    @staticmethod
    def from_env(env: Env):
        """
        Creates the RedisConfig object from environment variables.
        """
        redis_pass = env.str("REDIS_PASSWORD")
        redis_port = env.int("REDIS_PORT")
        redis_host = env.str("REDIS_HOST")

        return RedisConfig(
            redis_pass=redis_pass, redis_port=redis_port, redis_host=redis_host
        )


@dataclass
class Config:
    """
    The main configuration class that integrates all the other configuration classes.

    This class holds the other configuration classes, providing a centralized point of access for all settings.

    Attributes
    ----------
    tg_bot : TgBot
        Holds the settings related to the Telegram Bot.
    misc : Miscellaneous
        Holds the values for miscellaneous settings.
    db : Optional[DbConfig]
        Holds the settings specific to the database (default is None).
    redis : Optional[RedisConfig]
        Holds the settings specific to Redis (default is None).
    """

    tg_bot: TgBot
    db: DbConfig
    redis: Optional[RedisConfig] = None


def load_config(path: str = None) -> Config:
    """
    This function takes an optional file path as input and returns a Config object.
    :param path: The path of env file from where to load the configuration variables.
    It reads environment variables from a .env file if provided, else from the process environment.
    :return: Config object with attributes set as per environment variables.
    """

    # Create an Env object.
    # The Env object will be used to read environment variables.
    env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot.from_env(env),
        db=DbConfig.from_env(env),
        # redis=RedisConfig.from_env(env),
    )
