from sqlalchemy import select
from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings, get_settings
from acwa.models import Campaign
from acwa.security.crypto import TokenCipher
from acwa.services.accounts import connect_demo


def seed_demo(session: Session, clock: Clock, cipher: TokenCipher) -> None:
    if session.scalar(select(Campaign.id)) is not None:
        return
    account = connect_demo(session, cipher, clock, _demo_settings())
    now = clock.now()
    session.add(
        Campaign(
            account_id=account.id,
            name="Демонстрационная кампания",
            topic="Заметки о спокойной работе над своим проектом",
            context="Демонстрационные данные для проверки интерфейса. Это не настоящая публикация.",
            audience="Человек, который смотрит пробный сценарий",
            language="ru",
            tone="спокойный и конкретный",
            goal="Показать, как выглядит пост до включения расписания",
            desired_length="short",
            extra_instructions="Не обещай результат и не добавляй ссылки.",
            required_points="Это пример текста для прогрева, а не реклама.",
            forbidden="",
            examples="",
            allow_emoji=False,
            allow_hashtags=False,
            allow_links=False,
            publish_mode="manual",
            timezone="Europe/Moscow",
            weekdays=[1, 2, 3, 4, 5],
            times_of_day=["10:00"],
            starts_on=now.date(),
            ends_on=None,
            status="paused",
            schedule_cursor=now,
            created_at=now,
            updated_at=now,
        )
    )


def _demo_settings() -> Settings:
    return get_settings()
